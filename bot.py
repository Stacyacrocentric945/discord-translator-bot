"""
Discord Translator Bot (Final Production Version)
--------------------------------------------------
- Engine  : Google Gemini family (via google-genai)
- Logic   : Auto-detect source → translate to user's preferred target language
            (Default: AR <-> JA if no preference is set)
- Extras  : Audio transcription, per-user cooldowns, multi-model fallback,
            JSON-persistent preferences, atomic writes, task GC safety,
            file size validation, src_lang normalisation, guild rate limiting,
            embed sanitisation, memory-safe cooldown pruning
- Authors : testerxma (https://github.com/testerxma)
            uaaw      (https://github.com/uaaw)
"""

import asyncio
import json
import os
import shutil
import tempfile
import logging
from collections import deque
from typing import Optional
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from dotenv import load_dotenv

from google import genai
from google.genai import errors as genai_errors
from pydantic import BaseModel

# =========================================================
#  Logging
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# =========================================================
#  Environment
# =========================================================

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from your .env file!")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from your .env file!")

# =========================================================
#  Bot Meta — Owners & Credits
# =========================================================

BOT_VERSION   = "2.0.0"
BOT_NAME      = "Translator Bot"

OWNERS = [
    {
        "name":   "testerxma",
        "github": "https://github.com/testerxma",
    },
    {
        "name":   "uaaw",
        "github": "https://github.com/uaaw",
    },
]

def _owners_line() -> str:
    """Returns a formatted owners string for embeds/footers."""
    return " • ".join(f"[{o['name']}]({o['github']})" for o in OWNERS)

def _owners_plain() -> str:
    """Returns plain text owners string (no markdown links)."""
    return " & ".join(o["name"] for o in OWNERS)

# =========================================================
#  Tuneable Constants
# =========================================================

USER_COOLDOWN_SECONDS    = 15
MAX_AUDIO_SIZE_MB        = 20
MAX_AUDIO_SIZE_BYTES     = MAX_AUDIO_SIZE_MB * 1024 * 1024
MAX_EMBED_FIELD_LENGTH   = 1024
MAX_CONCURRENT_PER_GUILD = 3
GEMINI_RPM_LIMIT         = 10
GEMINI_SEMAPHORE_SIZE    = 1
MAX_FALLBACK_WAIT_SECS   = 8
MAX_RESPONSE_PREVIEW     = 200
PREFS_FILE               = "user_prefs.json"

# =========================================================
#  Language Support
# =========================================================

LANG_LABEL: dict[str, str] = {
    "ar": "🇸🇦 Arabic",
    "ja": "🇯🇵 Japanese",
    "en": "🇺🇸 English",
    "fr": "🇫🇷 French",
    "es": "🇪🇸 Spanish",
    "de": "🇩🇪 German",
    "ko": "🇰🇷 Korean",
    "zh": "🇨🇳 Chinese",
    "ru": "🇷🇺 Russian",
    "tr": "🇹🇷 Turkish",
    "it": "🇮🇹 Italian",
    "pt": "🇵🇹 Portuguese",
    "hi": "🇮🇳 Hindi",
    "id": "🇮🇩 Indonesian",
    "pl": "🇵🇱 Polish",
    "nl": "🇳🇱 Dutch",
    "th": "🇹🇭 Thai",
    "vi": "🇻🇳 Vietnamese",
}

LANG_CODE_ALIASES: dict[str, str] = {
    "arabic":       "ar",
    "japanese":     "ja",
    "english":      "en",
    "french":       "fr",
    "spanish":      "es",
    "german":       "de",
    "korean":       "ko",
    "chinese":      "zh",
    "russian":      "ru",
    "turkish":      "tr",
    "italian":      "it",
    "portuguese":   "pt",
    "hindi":        "hi",
    "indonesian":   "id",
    "polish":       "pl",
    "dutch":        "nl",
    "thai":         "th",
    "vietnamese":   "vi",
}

AUDIO_EXTS = {
    ".mp3", ".wav", ".ogg", ".m4a",
    ".webm", ".flac", ".opus", ".wma", ".aac",
}

# =========================================================
#  Gemini Setup
# =========================================================

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_PRIORITY = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


class TranslationResponse(BaseModel):
    src_lang:      str
    transcription: Optional[str] = None
    translation:   str


class QuotaExhaustedError(Exception):
    """Raised when all Gemini models hit quota limits or are unavailable."""
    pass


log.info("Gemini API initialised — %d models available", len(MODEL_PRIORITY))

# =========================================================
#  Rate Limiting — Sliding Window + Semaphore
# =========================================================

GEMINI_SEMAPHORE = asyncio.Semaphore(GEMINI_SEMAPHORE_SIZE)
_request_times: deque = deque(maxlen=GEMINI_RPM_LIMIT + 5)


def _is_retryable_error(e: genai_errors.ClientError) -> bool:
    return getattr(e, "code", None) in (429, 503)


async def _throttled_gemini_call(coro_fn):
    """Serialise all Gemini calls with sliding-window RPM enforcement."""
    async with GEMINI_SEMAPHORE:
        loop = asyncio.get_running_loop()
        now  = loop.time()

        while _request_times and now - _request_times[0] > 60.0:
            _request_times.popleft()

        if len(_request_times) >= GEMINI_RPM_LIMIT:
            wait = 60.0 - (now - _request_times[0])
            if wait > 0:
                log.info("RPM cap reached — sleeping %.1fs", wait)
                await asyncio.sleep(wait)

        try:
            result = await coro_fn()
            _request_times.append(asyncio.get_running_loop().time())
            return result
        except genai_errors.ClientError as e:
            if _is_retryable_error(e):
                raise
            raise


async def _try_generate_with_fallback(generate_fn) -> TranslationResponse:
    """Try each model with capped exponential back-off."""
    last_error   = None
    total_waited = 0.0

    for i, model_id in enumerate(MODEL_PRIORITY):
        try:
            loop = asyncio.get_running_loop()

            def _call(m=model_id):
                return generate_fn(m)

            response = await _throttled_gemini_call(
                lambda l=loop, c=_call: l.run_in_executor(None, c)
            )
            log.info("Success with model: %s", model_id)
            return response

        except genai_errors.ClientError as e:
            if _is_retryable_error(e):
                remaining = MAX_FALLBACK_WAIT_SECS - total_waited
                wait      = min(2 ** i, remaining)

                if wait <= 0:
                    log.warning(
                        "Model %s failed (%s) — max wait reached",
                        model_id, e.code,
                    )
                else:
                    log.warning(
                        "Model %s failed (%s) — retrying in %.1fs [%d/%d]",
                        model_id, e.code, wait, i + 1, len(MODEL_PRIORITY),
                    )
                    await asyncio.sleep(wait)
                    total_waited += wait

                last_error = e
                continue
            raise

    raise QuotaExhaustedError(
        f"All {len(MODEL_PRIORITY)} models exhausted."
    ) from last_error

# =========================================================
#  User Language Preferences  (JSON-backed, atomic writes)
# =========================================================

_user_prefs: dict[str, str] = {}


def _load_prefs() -> None:
    global _user_prefs
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                _user_prefs = json.load(f)
            log.info(
                "Loaded %d user preferences from %s",
                len(_user_prefs), PREFS_FILE,
            )
        except Exception as exc:
            log.warning("Could not load %s — starting fresh: %s", PREFS_FILE, exc)
            _user_prefs = {}


def _save_prefs() -> None:
    tmp_path = PREFS_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_user_prefs, f, ensure_ascii=False, indent=2)
        shutil.move(tmp_path, PREFS_FILE)
    except Exception as exc:
        log.warning("Failed to save preferences: %s", exc)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def get_user_lang(user_id: int) -> Optional[str]:
    return _user_prefs.get(str(user_id))


def set_user_lang(user_id: int, lang_code: str) -> None:
    _user_prefs[str(user_id)] = lang_code.lower().strip()
    _save_prefs()


def clear_user_lang(user_id: int) -> None:
    _user_prefs.pop(str(user_id), None)
    _save_prefs()


_load_prefs()

# =========================================================
#  Per-User Cooldowns  (auto-pruning)
# =========================================================

_user_cooldowns: dict[int, datetime] = {}


def is_user_on_cooldown(user_id: int) -> Optional[float]:
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=USER_COOLDOWN_SECONDS)

    expired = [uid for uid, ts in _user_cooldowns.items() if ts < cutoff]
    for uid in expired:
        del _user_cooldowns[uid]

    if user_id in _user_cooldowns:
        expiry = _user_cooldowns[user_id] + timedelta(seconds=USER_COOLDOWN_SECONDS)
        if now < expiry:
            return (expiry - now).total_seconds()
    return None


def set_user_cooldown(user_id: int) -> None:
    _user_cooldowns[user_id] = datetime.now(timezone.utc)

# =========================================================
#  Per-Guild Concurrency Limiting
# =========================================================

_guild_active_requests: dict[int, int] = {}


def _guild_increment(guild_id: int) -> bool:
    current = _guild_active_requests.get(guild_id, 0)
    if current >= MAX_CONCURRENT_PER_GUILD:
        return False
    _guild_active_requests[guild_id] = current + 1
    return True


def _guild_decrement(guild_id: int) -> None:
    count = _guild_active_requests.get(guild_id, 1)
    if count <= 1:
        _guild_active_requests.pop(guild_id, None)
    else:
        _guild_active_requests[guild_id] = count - 1

# =========================================================
#  Language Helpers
# =========================================================

def _normalise_lang_code(raw: str) -> str:
    cleaned = raw.lower().strip()
    if cleaned in LANG_LABEL:
        return cleaned
    if cleaned in LANG_CODE_ALIASES:
        return LANG_CODE_ALIASES[cleaned]
    short = cleaned[:2]
    if short in LANG_LABEL:
        return short
    log.warning("Unknown src_lang from Gemini: '%s' — defaulting to 'en'", raw)
    return "en"


def _get_target_lang(src: str, user_pref: Optional[str]) -> str:
    if user_pref:
        return user_pref
    defaults = {"ar": "ja", "ja": "ar"}
    return defaults.get(src, "en")

# =========================================================
#  Embed Helpers
# =========================================================

def _safe_embed_value(text: str, max_len: int = MAX_EMBED_FIELD_LENGTH) -> str:
    text = text.replace("@everyone", "@\u200beveryone")
    text = text.replace("@here",     "@\u200bhere")
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text or "\u200b"


def _base_embed(
    title: Optional[str] = None,
    color: int = 0x5865F2,
) -> discord.Embed:
    """Create a pre-styled embed with bot branding in the footer."""
    embed = discord.Embed(title=title, color=color)
    embed.set_footer(
        text=f"{BOT_NAME} v{BOT_VERSION} • Made by {_owners_plain()}"
    )
    return embed

# =========================================================
#  Prompt Builders
# =========================================================

def _build_text_prompt(target_lang: Optional[str] = None) -> str:
    if target_lang:
        label = LANG_LABEL.get(target_lang, target_lang)
        return (
            f"Detect the language of the text and translate it into "
            f"{target_lang} ({label}). "
            f"Return JSON: src_lang (ISO 639-1), transcription (null), translation."
        )
    return (
        "Detect the language of the text. "
        "If Arabic → translate to Japanese. "
        "If Japanese → translate to Arabic. "
        "Otherwise → translate to English. "
        "Return JSON: src_lang (ISO 639-1), transcription (null), translation."
    )


def _build_audio_prompt(target_lang: Optional[str] = None) -> str:
    if target_lang:
        label = LANG_LABEL.get(target_lang, target_lang)
        return (
            f"Transcribe this audio, detect its language, "
            f"then translate it into {target_lang} ({label}). "
            f"Return JSON: src_lang (ISO 639-1), transcription (original text), translation."
        )
    return (
        "Transcribe this audio and detect its language. "
        "If Arabic → translate to Japanese. "
        "If Japanese → translate to Arabic. "
        "Otherwise → translate to English. "
        "Return JSON: src_lang (ISO 639-1), transcription, translation."
    )

# =========================================================
#  Gemini Processing
# =========================================================

async def process_text(
    text: str,
    target_lang: Optional[str] = None,
) -> TranslationResponse:
    prompt = _build_text_prompt(target_lang)

    def _generate(model_id: str):
        return gemini_client.models.generate_content(
            model=model_id,
            contents=[prompt, text],
            config={
                "response_mime_type": "application/json",
                "response_schema":    TranslationResponse,
            },
        )

    response = await _try_generate_with_fallback(_generate)
    parsed   = response.parsed
    if parsed is None:
        raise ValueError(
            f"Gemini returned unparseable response: "
            f"{response.text[:MAX_RESPONSE_PREVIEW]}"
        )
    return parsed


async def process_audio(
    audio_path: str,
    target_lang: Optional[str] = None,
) -> TranslationResponse:
    prompt     = _build_audio_prompt(target_lang)
    audio_file = None

    try:
        def _upload():
            return gemini_client.files.upload(file=audio_path)

        audio_file = await _throttled_gemini_call(
            lambda: asyncio.get_running_loop().run_in_executor(None, _upload)
        )

        def _generate(model_id: str):
            return gemini_client.models.generate_content(
                model=model_id,
                contents=[audio_file, prompt],
                config={
                    "response_mime_type": "application/json",
                    "response_schema":    TranslationResponse,
                },
            )

        response = await _try_generate_with_fallback(_generate)
        parsed   = response.parsed
        if parsed is None:
            raise ValueError(
                f"Gemini returned unparseable response: "
                f"{response.text[:MAX_RESPONSE_PREVIEW]}"
            )
        return parsed

    finally:
        if audio_file is not None:
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: gemini_client.files.delete(name=audio_file.name),
                )
            except Exception as exc:
                log.warning("Failed to delete uploaded Gemini file: %s", exc)

# =========================================================
#  Audio Helpers
# =========================================================

def _is_audio_attachment(att: discord.Attachment) -> bool:
    ext     = os.path.splitext(att.filename.lower())[1]
    is_ext  = ext in AUDIO_EXTS
    is_mime = bool(att.content_type and "audio" in att.content_type)
    return is_ext or is_mime


async def download_audio(attachment: discord.Attachment) -> str:
    if attachment.size > MAX_AUDIO_SIZE_BYTES:
        raise ValueError(
            f"Audio file too large "
            f"({attachment.size / 1024 / 1024:.1f} MB). "
            f"Maximum: {MAX_AUDIO_SIZE_MB} MB."
        )
    ext      = os.path.splitext(attachment.filename.lower())[1] or ".ogg"
    tmp      = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        await attachment.save(tmp_path)
        return tmp_path
    except Exception:
        _cleanup(tmp_path)
        raise


def _cleanup(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass

# =========================================================
#  Core Request Handler
# =========================================================

async def handle_request(
    message:      discord.Message,
    original_msg: discord.Message,
) -> None:

    # ── Cooldown check ───────────────────────────────────
    cooldown = is_user_on_cooldown(message.author.id)
    if cooldown:
        await message.reply(
            f"⏳ Please wait **{int(cooldown)}s** before another translation."
        )
        return

    # ── Guild concurrency check ──────────────────────────
    guild_id = message.guild.id if message.guild else 0
    if not _guild_increment(guild_id):
        await message.reply(
            f"⏳ This server already has "
            f"**{MAX_CONCURRENT_PER_GUILD}** translations running. "
            f"Please wait a moment."
        )
        return

    target_lang = get_user_lang(message.author.id)
    tmp_path: Optional[str] = None

    try:
        async with message.channel.typing():

            # ── Find audio attachment ────────────────────
            audio_att = next(
                (a for a in original_msg.attachments if _is_audio_attachment(a)),
                None,
            )

            # ── Transcribe / translate ───────────────────
            if audio_att:
                try:
                    tmp_path = await download_audio(audio_att)
                except ValueError as exc:
                    await message.reply(f"⚠️ {exc}")
                    return
                res = await process_audio(tmp_path, target_lang=target_lang)
            else:
                text = original_msg.content.strip()
                if not text:
                    await message.reply("⚠️ That message has no text to translate.")
                    return
                res = await process_text(text, target_lang=target_lang)

            # ── Normalise & resolve languages ────────────
            src = _normalise_lang_code(res.src_lang)
            tgt = _get_target_lang(src, target_lang)

            # ── Build result embed ───────────────────────
            icon             = "🎙️" if audio_att else "💬"
            original_display = res.transcription or original_msg.content

            embed = _base_embed()
            embed.set_author(
                name=f"{icon} Message from {original_msg.author.display_name}",
                icon_url=original_msg.author.display_avatar.url,
            )
            embed.add_field(
                name=f"📝 Original ({LANG_LABEL.get(src, src.upper())})",
                value=_safe_embed_value(original_display),
                inline=False,
            )
            embed.add_field(
                name=f"🌍 Translation ({LANG_LABEL.get(tgt, tgt.upper())})",
                value=_safe_embed_value(res.translation),
                inline=False,
            )
            if target_lang:
                embed.add_field(
                    name="⚙️ Preference",
                    value=f"Targeting {LANG_LABEL.get(target_lang, target_lang)}",
                    inline=False,
                )

            await message.reply(embed=embed)
            set_user_cooldown(message.author.id)

    # ── Error Handling ────────────────────────────────────
    except QuotaExhaustedError:
        await message.reply(
            "🚫 **All translation models are at their limits.**\n"
            "Quotas reset daily (~midnight PT).\n"
            "Upgrade for unlimited usage: <https://ai.google.dev/gemini-api/docs/pricing>"
        )

    except genai_errors.ClientError as exc:
        log.exception("Gemini API error")
        code = getattr(exc, "code", None)

        if code == 429:
            retry_seconds = 60
            try:
                for detail in getattr(exc, "details", None) or []:
                    if detail.get("@type", "").endswith("RetryInfo"):
                        retry_seconds = int(
                            detail.get("retryDelay", "60s").replace("s", "")
                        )
            except Exception:
                pass
            await message.reply(
                f"🚫 **Rate limit hit!**\n"
                f"Please retry in **{retry_seconds}s**."
            )
        elif code == 503:
            await message.reply(
                "🚫 **Gemini servers are overloaded** (503).\n"
                "Please try again in a few minutes."
            )
        else:
            await message.reply(f"❌ Gemini API Error `{code}`: `{exc}`")

    except Exception as exc:
        log.exception("Unexpected error in handle_request")
        await message.reply(f"❌ Unexpected error: `{exc}`")

    finally:
        _cleanup(tmp_path)
        _guild_decrement(guild_id)

# =========================================================
#  Discord Bot Setup
# =========================================================

intents                 = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)

_background_tasks: set = set()

# =========================================================
#  Events
# =========================================================

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        log.info("Slash cmds  : %d synced", len(synced))
    except Exception as exc:
        log.warning("Slash command sync failed: %s", exc)

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  %s v%s", BOT_NAME, BOT_VERSION)
    log.info("  Made by: %s", _owners_plain())
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("Bot online  : %s (ID: %s)", bot.user, bot.user.id)
    log.info("Servers     : %d", len(bot.guilds))
    log.info("Models      : %d available", len(MODEL_PRIORITY))
    log.info("Languages   : %d supported", len(LANG_LABEL))
    log.info("Cooldown    : %ds per user", USER_COOLDOWN_SECONDS)
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="@mention + reply to translate",
        )
    )


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)

    if message.author.bot or bot.user not in message.mentions:
        return

    ctx = await bot.get_context(message)
    if ctx.valid:
        return

    if message.reference is None:
        await message.reply(
            f"👋 {message.author.mention} "
            f"**Reply to a message** and tag me to translate it!\n"
            f"Use `!help` for full command list."
        )
        return

    try:
        original = await message.channel.fetch_message(
            message.reference.message_id
        )
    except Exception as exc:
        await message.reply(f"❌ Could not fetch the original message: `{exc}`")
        return

    if original.author.bot:
        await message.reply("⚠️ I can't translate messages from bots.")
        return

    task = asyncio.create_task(handle_request(message, original))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

# =========================================================
#  Commands
# =========================================================

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    """Show all available commands and how to use the bot."""
    embed = _base_embed(title="📖 Help — All Commands")
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(
        name="🔤 How to Translate",
        value=(
            "**Reply** to any message and **mention the bot** `@BotName`.\n"
            "Supports both **text messages** and **audio attachments**.\n"
            "The bot auto-detects the source language."
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ Language Commands",
        value=(
            "`!lang [code]` — Set your personal target language\n"
            "`!langs`       — List all supported language codes\n"
            "`!resetlang`   — Clear your preference (restore default)\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="📊 Info Commands",
        value=(
            "`!status`      — Show bot stats and your current settings\n"
            "`!owners`      — Who made this bot\n"
            "`!help`        — Show this message\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="🌍 Default Behaviour",
        value=(
            "• **Arabic** → translated to **Japanese**\n"
            "• **Japanese** → translated to **Arabic**\n"
            "• **Any other language** → translated to **English**\n"
            "• Set a custom target with `!lang <code>` to override."
        ),
        inline=False,
    )
    embed.add_field(
        name="🎙️ Audio Support",
        value=(
            f"Max file size: **{MAX_AUDIO_SIZE_MB} MB**\n"
            f"Supported formats: `mp3 wav ogg m4a webm flac opus wma aac`"
        ),
        inline=False,
    )
    embed.add_field(
        name="⏱️ Limits",
        value=(
            f"• Per-user cooldown: **{USER_COOLDOWN_SECONDS}s** (after successful translation)\n"
            f"• Max concurrent per server: **{MAX_CONCURRENT_PER_GUILD}**\n"
            f"• Gemini fallback models: **{len(MODEL_PRIORITY)}**"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)


@bot.command(name="langs")
async def list_languages(ctx: commands.Context):
    """List all supported translation languages."""
    lines = [f"`{k}` — {v}" for k, v in sorted(LANG_LABEL.items())]
    embed = _base_embed(title="🌍 Supported Languages")
    embed.description = "\n".join(lines)
    embed.add_field(
        name="💡 Usage",
        value="`!lang <code>` — e.g. `!lang en` or `!lang ja`",
        inline=False,
    )
    await ctx.send(embed=embed)


@bot.command(name="lang")
async def set_language(ctx: commands.Context, lang_code: Optional[str] = None):
    """Set or view your personal translation target language."""
    if not lang_code:
        current = get_user_lang(ctx.author.id)
        embed   = _base_embed(title="⚙️ Your Language Setting")
        if current:
            embed.description = (
                f"Your current target language:\n"
                f"**{LANG_LABEL.get(current, current)}** (`{current}`)"
            )
        else:
            embed.description = (
                "You have **no custom target** set.\n"
                "Default: **Arabic ↔ Japanese** auto-swap.\n\n"
                "Set one with `!lang <code>` — see `!langs` for options."
            )
        await ctx.send(embed=embed)
        return

    lang_code = lang_code.lower().strip()
    if lang_code not in LANG_LABEL:
        codes = " ".join(f"`{k}`" for k in sorted(LANG_LABEL))
        embed = _base_embed(title="❌ Unknown Language Code", color=0xED4245)
        embed.description = f"Available codes:\n{codes}"
        await ctx.send(embed=embed)
        return

    set_user_lang(ctx.author.id, lang_code)
    embed = _base_embed(title="✅ Language Updated")
    embed.description = (
        f"{ctx.author.mention} your target language is now:\n"
        f"**{LANG_LABEL[lang_code]}** (`{lang_code}`)\n\n"
        f"All your translations will target this language."
    )
    await ctx.send(embed=embed)


@bot.command(name="resetlang")
async def reset_language(ctx: commands.Context):
    """Clear your custom language preference."""
    clear_user_lang(ctx.author.id)
    embed = _base_embed(title="✅ Language Preference Reset")
    embed.description = (
        f"{ctx.author.mention} your preference has been cleared.\n"
        f"Restored default: **Arabic ↔ Japanese** auto-swap."
    )
    await ctx.send(embed=embed)


@bot.command(name="status")
async def status_command(ctx: commands.Context):
    """Show bot stats and your personal settings."""
    guild_id   = ctx.guild.id if ctx.guild else 0
    active     = _guild_active_requests.get(guild_id, 0)
    user_lang  = get_user_lang(ctx.author.id)
    lang_label = (
        f"{LANG_LABEL.get(user_lang, user_lang)} (`{user_lang}`)"
        if user_lang
        else "Default (Arabic ↔ Japanese)"
    )
    cooldown   = is_user_on_cooldown(ctx.author.id)

    embed = _base_embed(title="📊 Bot Status")
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(
        name="🌍 Your Target Language",
        value=lang_label,
        inline=False,
    )
    embed.add_field(
        name="⏳ Your Cooldown",
        value=f"{int(cooldown)}s remaining" if cooldown else "Ready ✅",
        inline=True,
    )
    embed.add_field(
        name="🔄 Active Translations",
        value=f"{active} / {MAX_CONCURRENT_PER_GUILD}",
        inline=True,
    )
    embed.add_field(
        name="🤖 Gemini Models",
        value=str(len(MODEL_PRIORITY)),
        inline=True,
    )
    embed.add_field(
        name="🌐 Servers",
        value=str(len(bot.guilds)),
        inline=True,
    )
    embed.add_field(
        name="🗣️ Languages Supported",
        value=str(len(LANG_LABEL)),
        inline=True,
    )
    embed.add_field(
        name="📦 Version",
        value=f"v{BOT_VERSION}",
        inline=True,
    )
    await ctx.send(embed=embed)


@bot.command(name="owners")
async def owners_command(ctx: commands.Context):
    """Show information about the bot's creators."""
    embed = _base_embed(title="👑 Bot Owners & Credits")
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.description = (
        f"**{BOT_NAME}** `v{BOT_VERSION}` was created by:\n\u200b"
    )

    for owner in OWNERS:
        embed.add_field(
            name=f"👤 {owner['name']}",
            value=(
                f"[GitHub Profile]({owner['github']})\n"
                f"`{owner['github']}`"
            ),
            inline=True,
        )

    embed.add_field(
        name="\u200b",
        value=(
            "💡 Found a bug or want to contribute?\n"
            "Open an issue or PR on GitHub!"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)

# =========================================================
#  Entry Point
# =========================================================

bot.run(DISCORD_TOKEN)