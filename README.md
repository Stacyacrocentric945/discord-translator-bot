<div align="center">

# 🌍 Discord Translator Bot

**A powerful, production-ready Discord bot that auto-detects and translates
text & audio messages using Google Gemini AI.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0%2B-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![Gemini](https://img.shields.io/badge/Google-Gemini_AI-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Made with ❤️ by**
[testerxma](https://github.com/testerxma) • [uaaw](https://github.com/uaaw)

</div>

---

## Table of Contents

1. Features
2. Requirements
3. Installation
4. Configuration
5. Running the Bot
6. Commands
7. How to Use
8. Language Support
9. Audio Support
10. Architecture
11. Troubleshooting
12. Project Structure
13. Credits

---

## 1. Features

- Text Translation
  Translate any text message by replying to it and mentioning the bot.

- Audio Transcription and Translation
  Upload audio files — the bot transcribes and translates them automatically.

- 18 Supported Languages
  Arabic, Japanese, English, French, Spanish, German, Korean, Chinese,
  Russian, Turkish, Italian, Portuguese, Hindi, Indonesian, Polish,
  Dutch, Thai, Vietnamese.

- Multi-Model Fallback
  Six Gemini models are tried in sequence to maximise free-tier uptime.

- Automatic Language Detection
  No need to specify the source language — Gemini detects it automatically.

- Per-User Language Preferences
  Each user can set their own target language, saved across restarts.

- Rate Limiting
  Per-user cooldowns and per-guild concurrency limits prevent abuse.

- Persistent Storage
  User preferences are saved to user_prefs.json using atomic writes.

- Sliding Window RPM Control
  Respects Gemini API rate limits with a sliding window algorithm.

- Safe Embed Output
  Escaped @everyone and @here tokens in all translated content.

---

## 2. Requirements

  Python          3.10 or higher
  discord.py      2.0  or higher
  google-genai    1.0  or higher
  pydantic        2.0  or higher
  python-dotenv   any version

---

## 3. Installation

### Step 1 — Clone the Repository

    git clone https://github.com/testerxma/discord-translator-bot.git
    cd discord-translator-bot

### Step 2 — Create a Virtual Environment

    Windows:
        python -m venv venv
        venv\Scripts\activate

    macOS and Linux:
        python3 -m venv venv
        source venv/bin/activate

### Step 3 — Install Dependencies

    pip install -r requirements.txt

    Contents of requirements.txt:

        discord.py>=2.0.0
        google-genai>=1.0.0
        pydantic>=2.0.0
        python-dotenv>=1.0.0

### Step 4 — Create the .env File

Create a file named .env in the project root directory:

    DISCORD_TOKEN=your_discord_bot_token_here
    GEMINI_API_KEY=your_gemini_api_key_here

    Rules:
        - No spaces around the equals sign
        - No quotes around the values
        - Never share or commit this file

Add it to .gitignore immediately:

    echo ".env" >> .gitignore

---

## 4. Configuration

### 4.1 Discord Bot Token

    1. Go to https://discord.com/developers/applications
    2. Click "New Application" and give it a name
    3. Go to "Bot" in the left sidebar
    4. Click "Reset Token" and copy the token
    5. Paste it into your .env file as DISCORD_TOKEN=

### 4.2 Enable Required Intents

    Go to:
        Discord Developer Portal
        -> Your Application
        -> Bot
        -> Privileged Gateway Intents

    Enable the following:

        [x] Presence Intent
        [x] Server Members Intent
        [x] Message Content Intent       <- Required

### 4.3 Invite the Bot to Your Server

    Go to:
        Discord Developer Portal
        -> Your Application
        -> OAuth2
        -> URL Generator

    Select Scopes:
        [x] bot
        [x] applications.commands

    Select Bot Permissions:

        General:
            [x] View Channels

        Text:
            [x] Send Messages
            [x] Send Messages in Threads
            [x] Embed Links
            [x] Attach Files
            [x] Read Message History
            [x] Use Slash Commands

        Voice:
            [x] Connect
            [x] Speak
            [x] Use Voice Activity

    Copy the generated URL and open it in your browser to invite the bot.

    Permissions Integer : 2184301632

    Direct invite link (replace CLIENT_ID with your bot's application ID):
        https://discord.com/oauth2/authorize?client_id=CLIENT_ID&permissions=2184301632&integration_type=0&scope=bot+applications.commands

### 4.4 Gemini API Key

    1. Go to https://aistudio.google.com/app/apikey
    2. Click "Create API Key"
    3. Copy the key
    4. Paste it into your .env file as GEMINI_API_KEY=

    Note:
        The free tier includes generous daily limits.
        The bot automatically rotates through 6 Gemini models
        to maximise free-tier uptime before hitting limits.

### 4.5 Optional — Tuning Constants

    These values can be adjusted at the top of bot.py:

        USER_COOLDOWN_SECONDS    = 15
            Seconds a user must wait between translation requests.

        MAX_AUDIO_SIZE_MB        = 20
            Maximum allowed audio file size in megabytes.

        MAX_CONCURRENT_PER_GUILD = 3
            Maximum simultaneous translations allowed per server.

        GEMINI_RPM_LIMIT         = 10
            Maximum Gemini API requests per 60-second window.

        MAX_FALLBACK_WAIT_SECS   = 8
            Maximum total seconds spent on model fallback retries.

---

## 5. Running the Bot

### Standard Start

    python bot.py

### Expected Startup Output

    13:00:00 [INFO] Gemini API initialised — 6 models available
    13:00:00 [INFO] Loaded 3 user preferences from user_prefs.json
    13:00:01 [INFO] ----------------------------------------
    13:00:01 [INFO]   Translator Bot v2.0.0
    13:00:01 [INFO]   Made by: testerxma & uaaw
    13:00:01 [INFO] ----------------------------------------
    13:00:01 [INFO] Bot online  : TranslatorBot#1234 (ID: 123456789)
    13:00:01 [INFO] Servers     : 1
    13:00:01 [INFO] Models      : 6 available
    13:00:01 [INFO] Languages   : 18 supported
    13:00:01 [INFO] Cooldown    : 15s per user
    13:00:01 [INFO] ----------------------------------------

### Running as a Background Service

    Windows — using pythonw (no console window):

        pythonw bot.py

    Linux — using systemd:

        Create the file /etc/systemd/system/translator-bot.service
        with the following content:

            [Unit]
            Description=Discord Translator Bot
            After=network.target

            [Service]
            Type=simple
            User=your_linux_username
            WorkingDirectory=/path/to/bot
            ExecStart=/path/to/venv/bin/python bot.py
            Restart=on-failure
            RestartSec=5

            [Install]
            WantedBy=multi-user.target

        Then run:

            sudo systemctl enable translator-bot
            sudo systemctl start translator-bot
            sudo systemctl status translator-bot

---

## 6. Commands

### Translation (No Command Needed)

    Action          : Translate a text message
    How             : Reply to the message and mention @BotName

    Action          : Translate an audio file
    How             : Reply to the message containing the audio and mention @BotName

---

### !help

    Description : Show the full help menu with all commands and usage examples.
    Usage       : !help

---

### !lang [code]

    Description : Set your personal target translation language.
                  Run with no argument to view your current setting.
    Usage       : !lang <code>
    Examples    :
                  !lang en        Set target language to English
                  !lang ja        Set target language to Japanese
                  !lang ar        Set target language to Arabic
                  !lang fr        Set target language to French
                  !lang           View your current language setting

---

### !langs

    Description : List all 18 supported language codes.
    Usage       : !langs

    Output:
        ar  —  Arabic
        de  —  German
        en  —  English
        es  —  Spanish
        fr  —  French
        hi  —  Hindi
        id  —  Indonesian
        it  —  Italian
        ja  —  Japanese
        ko  —  Korean
        nl  —  Dutch
        pl  —  Polish
        pt  —  Portuguese
        ru  —  Russian
        th  —  Thai
        tr  —  Turkish
        vi  —  Vietnamese
        zh  —  Chinese

---

### !resetlang

    Description : Clear your custom language preference.
                  Restores the default Arabic <-> Japanese auto-swap behaviour.
    Usage       : !resetlang

---

### !status

    Description : Show the bot's current stats and your personal settings.
    Usage       : !status

    Shows:
        - Your current target language
        - Your cooldown status (ready or seconds remaining)
        - Active translations running in this server
        - Number of Gemini models available
        - Total servers the bot is in
        - Bot version number

---

### !owners

    Description : Display information about the bot's creators with GitHub links.
    Usage       : !owners

---

## 7. How to Use

### Translating a Text Message

    Step 1  Find any message in the server you want to translate.
    Step 2  Right-click the message and select "Reply".
    Step 3  In your reply, type @BotName (mention the bot).
    Step 4  Send the message.

    The bot will:
        - Auto-detect the source language
        - Apply your personal target language (or use the default)
        - Reply with a formatted embed showing the original and translation

    Example:

        User A writes  :  konnichiwa, genki desu ka?
        User B replies :  @TranslatorBot

        Bot replies:

            Message from User A
            -------------------
            Original (Japanese)
            konnichiwa, genki desu ka?

            Translation (Arabic)
            marhaban, kayfa haluk?

### Translating an Audio File

    Step 1  Find a message that contains an audio attachment.
    Step 2  Reply to that message and mention @BotName.
    Step 3  The bot will:
                a. Download the audio file
                b. Upload it to Gemini for transcription
                c. Translate the transcribed text
                d. Show both the transcript and the translation

### Setting a Personal Target Language

    Step 1  Run: !lang en
    Step 2  All translations YOU request will now target English.
    Step 3  Other users are unaffected — preferences are per-user.
    Step 4  Run: !resetlang to go back to the default behaviour.

### Default Translation Logic (No Preference Set)

    Source Language     ->    Target Language
    ----------------------------------------
    Arabic              ->    Japanese
    Japanese            ->    Arabic
    Any other language  ->    English

---

## 8. Language Support

    Code    Language        
    ----    --------        
    ar      Arabic          
    de      German          
    en      English         
    es      Spanish         
    fr      French          
    hi      Hindi           
    id      Indonesian      
    it      Italian         
    ja      Japanese        
    ko      Korean          
    nl      Dutch           
    pl      Polish          
    pt      Portuguese      
    ru      Russian         
    th      Thai            
    tr      Turkish         
    vi      Vietnamese      
    zh      Chinese         

    To add more languages, edit the LANG_LABEL and LANG_CODE_ALIASES
    dictionaries in bot.py.

---

## 9. Audio Support

### Supported Formats

    Format      Extension
    ------      ---------
    MP3         .mp3
    WAV         .wav
    OGG         .ogg
    M4A         .m4a
    WebM        .webm
    FLAC        .flac
    Opus        .opus
    WMA         .wma
    AAC         .aac

### Limits

    Maximum file size   : 20 MB (configurable via MAX_AUDIO_SIZE_MB in bot.py)
    Processing time     : 5 to 15 seconds depending on file length and model load

---

## 10. Architecture

    bot.py
    |
    |-- Environment and Constants
    |       DISCORD_TOKEN, GEMINI_API_KEY loaded from .env
    |       All tuneable limits defined at the top of the file
    |
    |-- Gemini Layer
    |       _throttled_gemini_call()       Sliding-window RPM + semaphore lock
    |       _try_generate_with_fallback()  6-model waterfall with backoff
    |       process_text()                 Text input  -> TranslationResponse
    |       process_audio()                Audio input -> TranslationResponse
    |
    |-- User Preferences
    |       user_prefs.json                Persistent JSON storage
    |       _load_prefs() / _save_prefs()  Atomic writes using .tmp file
    |       get_user_lang()                Read user preference
    |       set_user_lang()                Write user preference
    |       clear_user_lang()              Delete user preference
    |       is_user_on_cooldown()          Auto-pruning cooldown tracker
    |
    |-- Safety and Limits
    |       _guild_increment/decrement()   Per-guild concurrency counter
    |       _safe_embed_value()            Escapes @everyone and @here
    |       _normalise_lang_code()         Normalises Gemini language output
    |       download_audio()               Size check before file download
    |
    |-- Discord Bot
            on_ready()                     Sync commands, log startup info
            on_message()                   Detect mentions + reply references
            handle_request()               Main translation orchestrator
            Commands:
                !help
                !lang
                !langs
                !resetlang
                !status
                !owners

---

## 11. Troubleshooting

### Bot does not respond to mentions

    Check the following:
        - MESSAGE CONTENT INTENT is enabled in the Developer Portal
        - Bot has "Read Message History" permission in the channel
        - Bot role is not restricted by other server roles
        - You are replying to a message, not sending a new one

### Error: PrivilegedIntentsRequired on startup

    Go to:
        https://discord.com/developers/applications
        -> Your Application
        -> Bot
        -> Privileged Gateway Intents
        -> Enable: MESSAGE CONTENT INTENT
        -> Save Changes
        -> Restart the bot

### Error: TypeError: Files.upload() got an unexpected keyword argument 'path'

    Your google-genai SDK is outdated. Run:

        pip install --upgrade google-genai

    The API changed from:
        gemini_client.files.upload(path=audio_path)   <- Old, broken
    To:
        gemini_client.files.upload(file=audio_path)   <- New, correct

### Error: DISCORD_TOKEN is missing

    Check the following:
        - The .env file exists in the same folder as bot.py
        - It contains the line:  DISCORD_TOKEN=your_token_here
        - There are no spaces around the equals sign
        - There are no quotes around the token value

### Translation targets the wrong language

    Run:   !lang        to see your current preference
    Run:   !resetlang   to clear it
    Run:   !lang en     to set a new target language

### All Gemini models are quota exhausted

    The bot cycles through 6 Gemini models automatically.
    If all are exhausted:

        - Free tier quotas reset daily at approximately midnight Pacific Time
        - Wait and try again the next day
        - Or upgrade to a paid Gemini API plan:
          https://ai.google.dev/gemini-api/docs/pricing

### Bot says the server is busy

    The server has reached MAX_CONCURRENT_PER_GUILD (default: 3)
    simultaneous translation requests.

        - Wait for current translations to finish
        - Or increase MAX_CONCURRENT_PER_GUILD in bot.py

---

## 12. Project Structure

    discord-translator-bot/
    |
    |-- bot.py                Main bot file
    |-- .env                  Your secrets — never commit this file
    |-- .env.example          Template showing required variables
    |-- .gitignore            Excludes .env and other files from git
    |-- requirements.txt      Python package dependencies
    |-- user_prefs.json       Auto-created on first !lang command
    |-- README.md             This file

### .env.example

    # Copy this file to .env and fill in your real values
    # Never commit your actual .env file to version control

    DISCORD_TOKEN=your_discord_bot_token_here
    GEMINI_API_KEY=your_gemini_api_key_here

### .gitignore

    # Secrets
    .env

    # Python
    __pycache__/
    *.pyc
    *.pyo
    venv/
    .venv/

    # Bot runtime data
    user_prefs.json
    user_prefs.json.tmp

    # OS files
    .DS_Store
    Thumbs.db
    desktop.ini

    # IDE files
    .vscode/
    .idea/
    *.swp

### requirements.txt

    discord.py>=2.0.0
    google-genai>=1.0.0
    pydantic>=2.0.0
    python-dotenv>=1.0.0

---

## 13. Credits

    Name          Role                    GitHub
    ----------    --------------------    ----------------------------------
    testerxma     Co-Creator, Developer   https://github.com/testerxma
    uaaw          Co-Creator, Developer   https://github.com/uaaw

---

## License

    MIT License

    Free to use, modify, and distribute.
    Please credit the original authors if you build upon this project.

---

    Translator Bot v2.0.0
    Made by testerxma (https://github.com/testerxma)
         and uaaw     (https://github.com/uaaw)
