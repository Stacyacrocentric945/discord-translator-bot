# 🎙️ Discord Voice → Transcribe + Translate Bot
### 100% Local AI — No API keys, No costs, No internet after setup

---

## 🧠 AI Models Used

| Task | Model | Size | Quality |
|---|---|---|---|
| 🎤 Speech → Text | OpenAI Whisper `base` | ~300MB | Excellent for EN/JA/AR |
| 🌍 EN ↔ Arabic | Helsinki-NLP `opus-mt-en-ar` | ~300MB | Very good |
| 🌍 EN ↔ Japanese | Helsinki-NLP `opus-mt-en-jap` | ~300MB | Very good |
| 🌍 AR ↔ JA | Pivots through English automatically | — | Good |

**Total download**: ~1.2GB (only once, then cached locally)

---

## ✨ Features

- 🎙️ Records voice from Discord voice channels
- 📝 Transcribes speech using **Whisper** (auto-detects language)
- 🌍 Translates between **English, Japanese, Arabic**
- 👥 Handles multiple speakers at once
- 💬 Clean Discord embeds per speaker
- 💰 **Completely free** — runs on your own machine

---

## 🚀 Setup (step by step)

### 1. Install Python 3.10+
Download from https://www.python.org/downloads/

### 2. Install FFmpeg (required for voice recording)
- **Windows**: Download from https://ffmpeg.org → add the `bin` folder to your PATH
- **Linux**: `sudo apt install ffmpeg`
- **Mac**: `brew install ffmpeg`

### 3. Install Python packages
```bash
pip install -r requirements.txt
```
> ⚠️ `torch` is large (~2GB). This may take 5-10 minutes.

### 4. Create your Discord Bot
1. Go to https://discord.com/developers/applications
2. Click **New Application** → give it a name
3. Go to **Bot** tab → **Add Bot**
4. Enable these **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Copy the **Bot Token**

### 5. Configure .env
Rename `.env.example` → `.env` and paste your token:
```
DISCORD_TOKEN=paste_your_token_here
```

### 6. Invite the bot to your server
1. In Developer Portal → **OAuth2 → URL Generator**
2. Scopes: ✅ `bot` + ✅ `applications.commands`
3. Bot Permissions: ✅ Connect, ✅ Speak, ✅ Send Messages, ✅ Use Slash Commands
4. Open the URL and invite the bot

### 7. Run!
```bash
python bot.py
```

First run will download the Whisper model (~300MB). Use `/preload` in Discord to download all translation models at once.

---

## 🎮 Bot Commands

| Command | What it does |
|---|---|
| `/join` | Bot enters your voice channel and starts recording |
| `/stop` | Stops — transcribes and translates everything |
| `/language` | Change the target translation language |
| `/status` | Check if bot is recording and current settings |
| `/preload` | Download all AI models now (recommended first-time) |

---

## ⚡ Performance Tips

- **Slow PC?** Change `WHISPER_MODEL_SIZE = "tiny"` in bot.py — smaller/faster but slightly less accurate
- **NVIDIA GPU?** Replace `torch==2.3.1` in requirements.txt with the CUDA version for much faster processing
- Models are cached after first download — restarts are fast

---

## 🔄 How it works

```
User speaks in voice channel
        ↓
[Whisper] Converts audio → text (detects language automatically)
        ↓
[Helsinki-NLP] Translates text to your chosen language
        ↓
Bot posts embed in text channel with original + translation
```

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `FFmpeg not found` | Install FFmpeg and add to PATH |
| Bot not responding to `/join` | Wait up to 1 hour for slash commands to sync globally |
| `No audio captured` | Make sure you spoke before running `/stop` |
| Very slow translation | Use a GPU, or switch Whisper to `tiny` model |
| `torch` install fails | Try: `pip install torch --index-url https://download.pytorch.org/whl/cpu` |