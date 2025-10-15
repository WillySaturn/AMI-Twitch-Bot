# A.M.I. - An Interactive Stream Companion

A custom Twitch bot built with Python, designed from the ground up to be more than just a chat moderator. A.M.I. (Artificial Module Intelligence) serves as a fully interactive co-host with the personality of a SEGA Dreamcast, providing robust moderation, community entertainment, and deep integration with the live stream itself.

## Key Features

    🧠 Dual-Mode Conversational Core: Seamlessly answers user questions using Google's Gemini model, with an automatic fallback to a robust, keyword-based preset response system to ensure 100% uptime.

    🛡️ Advanced Auto-Moderation: A multi-tiered, zero-tolerance moderation system featuring escalating punishments, link protection, and word normalization to catch bypassed slurs. The system's logic is managed through external, .gitignore'd text files for safety and easy updates.

    🎬 Deep OBS & Stream Integration: Connects directly to OBS via websockets to control on-screen sources, trigger animations, and update text labels in real-time based on chat commands and stream events.

    🎤 High-Quality Text-to-Speech: Utilizes Amazon Polly to generate natural, expressive voice lines for all announcements, alerts, and AI-driven responses.

    🎮 Interactive Games & Commands: Drives community engagement with a full-featured, multi-round trivia game (including categories, difficulties, and leaderboards) alongside a suite of fun commands like !8ball and !rps.

    ✨ Real-Time Event Reactions: Listens for follows, subscriptions (new, resub, and gifted), raids, and cheers/bits, triggering unique, tiered TTS alerts and on-screen events for each.

## Feature Deep Dive

### Dual-Mode Conversational AI

A.M.I.'s primary !askami command is powered by the Google Gemini API, allowing her to answer a wide range of questions while staying in character as a retro-gaming robot. In the event of an API outage, the system is designed to fail gracefully. A complete, non-AI backup version of the bot can be run, which uses a comprehensive dictionary of keywords to provide preset, in-character responses, ensuring the bot's core personality and functions remain available at all times.

### Advanced, Multi-Tiered Moderation

A.M.I.'s moderation suite is designed for precision and scalability.

    Strike System: Separate JSON files track user infractions for general rule-breaking (e.g., posting unauthorized links, political talk) and toxicity. Punishments automatically escalate from message deletion to timeouts and eventual bans.

    Dynamic Wordlists: All banned words and phrases are stored in external .txt files, which are kept private via .gitignore. This allows for easy and safe updates to moderation lists without altering the source code.

    Bypass Detection: A normalization function strips symbols and converts leetspeak (e.g., h@t3 -> hate) before checking messages, ensuring that attempts to bypass the filter are caught.

### Deep OBS & Stream Integration

A.M.I. acts as a true stream companion by directly interacting with the broadcast.

    Real-Time Alerts: Using Twitch EventSub and the Streamlabs API, she provides instant, voiced thank-yous for follows, subs, raids, and cheers. Cheer alerts are tiered, with more excited reactions for larger amounts. Gifted subs, including mass gifts, trigger a "sub bomb" alert.

    OBS Control: She can trigger on-screen animations for special events and easter eggs, control the visibility of sources, and update text files used for on-screen labels (like "Latest Follower").

    External Webhooks: A built-in web server listens for POST requests from services like Ko-fi, allowing for real-time, on-stream donation alerts.
