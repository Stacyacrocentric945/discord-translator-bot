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

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Running the Bot](#-running-the-bot)
- [Commands](#-commands)
- [How to Use](#-how-to-use)
- [Language Support](#-language-support)
- [Audio Support](#-audio-support)
- [Architecture](#-architecture)
- [Troubleshooting](#-troubleshooting)
- [Credits](#-credits)

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔤 **Text Translation** | Translate any text message by replying and mentioning the bot |
| 🎙️ **Audio Transcription** | Upload audio files — bot transcribes AND translates them |
| 🌍 **18 Languages** | Arabic, Japanese, English, French, Spanish, German, Korean, Chinese + more |
| 🤖 **Multi-Model Fallback** | 6 Gemini models tried in sequence — maximises free-tier uptime |
| 🔁 **Auto Language Detection** | No need to specify source language — Gemini detects it automatically |
| ⚙️ **Per-User Preferences** | Each user can set their own target language — saved across restarts |
| 🛡️ **Rate Limiting** | Per-user cooldowns + per-guild concurrency limits |
| 💾 **Persistent Storage** | User preferences saved to `user_prefs.json` with atomic writes |
| 📊 **Sliding Window RPM** | Respects Gemini API rate limits with a smart sliding window |
| 🔒 **Safe Embeds** | Escapes `@everyone` / `@here` in translated content |

---

## 📦 Requirements

| Requirement | Minimum Version |
|---|---|
| Python | `3.10` or higher |
| discord.py | `2.0` or higher |
| google-genai | `1.0` or higher |
| pydantic | `2.0` or higher |
| python-dotenv | any |

---

## 🚀 Installation

### Step 1 — Clone the Repository

```bash
git clone https://github.com/testerxma/discord-translator-bot.git
cd discord-translator-bot
