# A.M.I. - An Interactive Stream Companion
A custom Twitch bot built with Python, designed from the ground up to be more than just a chat moderator. A.M.I. (Artificial Module Intelligence) serves as a fully interactive co-host with the personality of a SEGA Dreamcast, providing robust moderation, community entertainment, and deep integration with the live stream itself.

---
## Key Features
* 🧠 **Dual-Mode Conversational Core:** Seamlessly answers user questions using Google's Gemini model, with an automatic fallback to a robust, keyword-based preset response system to ensure 100% uptime.
* 🛡️ **Advanced Auto-Moderation:** A multi-tiered, zero-tolerance moderation system featuring escalating punishments, link protection, and word normalization to catch bypassed slurs.
* 🎬 **Deep OBS & Stream Integration:** Connects directly to OBS via websockets to control on-screen sources, trigger animations, and update text labels in real-time.
* 🎤 **High-Quality Text-to-Speech:** Utilizes Amazon Polly to generate natural, expressive voice lines for all announcements, alerts, and AI-driven responses.
* 🎮 **Interactive Games & Commands:** Drives community engagement with a full-featured trivia game (including leaderboards) alongside a suite of fun commands like `!8ball` and `!rps`.
* ✨ **Real-Time Event Reactions:** Listens for follows, subscriptions, raids, and cheers, triggering unique, tiered TTS alerts and on-screen events for each.

---
## Feature Deep Dive

#### Dual-Mode Conversational AI
A.M.I.'s primary `!askami` command is powered by the Google Gemini API, allowing her to answer a wide range of questions while staying in character. In the event of an API outage, the system is designed to fail gracefully. A complete, non-AI backup version of the bot can be run which uses a comprehensive dictionary of keywords to provide preset responses, ensuring the bot's core personality remains available at all times.

#### Advanced, Multi-Tiered Moderation
A.M.I.'s moderation suite is designed for precision and scalability. It features a strike system that tracks infractions in JSON files, dynamic wordlists stored in external `.txt` files for easy updates, and a normalization function that converts leetspeak (e.g., `h@t3` -> `hate`) to catch users attempting to bypass the filter.

#### Deep OBS & Stream Integration
A.M.I. acts as a true stream companion by directly interacting with the broadcast using Twitch EventSub, the Streamlabs API, and local webhooks. She provides instant, voiced thank-yous for events and can trigger on-screen animations, control source visibility, and update text files used for OBS labels (like "Latest Follower").

---
## 💻 Tech Stack
* **Core Language:** Python 3
* **AI:** Google Gemini API
* **Text-to-Speech:** Amazon Polly
* **Stream Events:** Twitch EventSub & Streamlabs API
* **OBS Integration:** `obs-websocket`
* **Dependencies:** `python-dotenv`, `requests`, `pydub`, `socketio[client]`

---
## 📋 Requirements
Please note that the primary version of the bot (`bot_new.py`) is designed with the assumption that the user's Twitch channel has **Affiliate** or **Partner** status.

This is because several core features rely on APIs that are only available to these accounts, including:
* **Channel Point Redemptions**
* **Subscription Alerts** (new, resub, gifted)
* **Cheer/Bit Alerts**

For channels that are not yet Affiliate or Partner, the **`bot_backup.py`** version is a better starting point.

---
## 🤖 Bot Versions
This repository contains three distinct versions of the A.M.I. bot, each with a specific purpose:

* **`bot_new.py` (Primary Bot):** The main, stable version of A.M.I. It includes all features and the full integration with Google's Gemini API. This is the script intended for normal operation.
* **`bot_experimental.py` (Development Bot):** The unstable testing ground. New features and experimental changes are implemented here first. It may contain bugs and is not recommended for a live stream.
* **`bot_backup.py` (Backup Bot - Non-AI):** A fallback version designed for maximum stability. It contains all features *except* for the AI integration and uses a preset, keyword-based response system for the `!askami` command.

---
## ⚙️ Setup & Configuration
A.M.I. uses a `.env` file to securely manage all API keys and configuration variables.

1.  **Create the `.env` file:** In the root directory of the project, create a new file named exactly `.env`.
2.  **Add Configuration Variables:** Copy the contents of the `.env.example` file into your new `.env` file.
3.  **Fill in Your Credentials:** Fill in the value for each variable. These are your personal keys, tokens, and settings.
4.  **Security:** Ensure your `.gitignore` file contains the line `.env` to prevent your secret keys from ever being uploaded to GitHub.

---
## 🔧 Key Customization Points
A.M.I. has been designed to be easily customized through several key files and variables.

#### 🧠 AI Persona (`AMI_PERSONA`)
The entire personality of the AI is defined within the `AMI_PERSONA` string variable in **`bot_new.py`**. By editing this text, you can fundamentally change how A.M.I. behaves, including her backstory, interests, and tone.

#### ❓ Trivia Questions (`trivia_questions.json`)
All questions for the `!trivia` command are stored in the **`trivia_questions.json`** file. You can add your own categories, difficulties, questions, and answers by following the existing JSON structure. Each question requires a `"question"` string and an `"answer"` array.
```json
{
  "sega": {
    "easy": [
      {
        "question": "What color is Sonic the Hedgehog?",
        "answer": ["blue"]
      }
    ]
  }
}
