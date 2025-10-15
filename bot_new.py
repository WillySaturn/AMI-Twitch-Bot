# ==============================================================================
# A.M.I. - WillySaturn's Interactive Twitch Bot (v76)
# ==============================================================================
# This version fixes critical errors in the Streamlabs and EventSub listeners
# to prevent crashes from empty messages and incomplete logic.
# ==============================================================================

import os
import json
import datetime
import shutil
import socket
import time
import threading
import google.generativeai as genai
import subprocess
import socketio
import boto3
import random
import sys
from queue import Queue
from pydub import AudioSegment
from pydub.playback import play as pydub_play
import io
from dotenv import load_dotenv, set_key
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer, BaseHTTPRequestHandler # <-- MODIFIED
import urllib.parse # <-- ADDED
from obswebsocket import obsws, requests
import re
from google.api_core import exceptions

# --- EventSub & API Imports ---
import asyncio
import websockets
import uuid
import requests as http_requests

# --- SETUP AND CONFIGURATION ---
load_dotenv()

# --- Connection Details ---
TOKEN = os.getenv('TMI_TOKEN')
NICK = os.getenv('BOT_NICK')
CHANNEL = os.getenv('CHANNEL')  # Twitch Channel
HOST = "irc.chat.twitch.tv"
PORT = 6667
STREAMLABS_TOKEN = os.getenv('STREAMLABS_SOCKET_TOKEN')
OBS_HOST = "localhost"
OBS_PORT = os.getenv('OBS_WEBSOCKET_PORT')
OBS_PASSWORD = os.getenv('OBS_WEBSOCKET_PASSWORD')
OBS_SOURCE_NAME = "A.M.I."

# --- EventSub Details ---
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
EVENTSUB_OAUTH_TOKEN = os.getenv('EVENTSUB_OAUTH_TOKEN') or os.getenv('PUBSUB_OAUTH_TOKEN') # Legacy support
TWITCH_USER_ID = os.getenv('TWITCH_USER_ID')

# --- Refresh Tokens ---
TMI_REFRESH_TOKEN = os.getenv('TMI_REFRESH_TOKEN')
EVENTSUB_REFRESH_TOKEN = os.getenv('EVENTSUB_REFRESH_TOKEN')
ENV_FILE_PATH = '.env'

# --- Metroid Minigame Configuration & State ---
METROID_MODE = os.getenv('METROID_MODE', 'FALSE').upper() == 'TRUE'
ARTIFACT_FILE = 'artifacts.json'
artifacts_data = {"collected_artifacts": [], "all_ghosts_defeated": False}
ALL_ARTIFACTS = [
    "Artifact_Truth", "Artifact_Strength", "Artifact_Elder", "Artifact_Wild",
    "Artifact_Lifegiver", "Artifact_Warrior", "Artifact_Chozo", "Artifact_Nature",
    "Artifact_Sun", "Artifact_World", "Artifact_Spirit", "Artifact_Newborn"
]

minigame_enabled = True
minigame_active = False
artifact_spawned = False
artifact_name = ""
active_ghosts = {}

super_missile_count = 5
weapon_charge = {"charge_beam": 0, "super_missile": 0}
weapon_cooldowns = {"charge_beam": 0, "super_missile": 0}
spawn_timestamps = []

# --- API Clients & Models ---
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash')
polly_client = boto3.client('polly')
sio = socketio.Client()
twitch_socket = None

# --- File Paths & Global State ---
TEXT_OVERLAY_FILE = 'ami_speech.txt'
STRIKE_FILE = 'strikes.json'
TOXICITY_STRIKE_FILE = 'toxicity_strikes.json'
INFRACTION_STRIKE_FILE = 'infraction_strikes.json'
STATE_FILE = 'ami_state.txt'
TRIVIA_FILE = 'trivia_questions.json'
TRIVIA_SCORES_FILE = 'trivia_scores.json'
DEATH_COUNTER_FILE = 'death_counter.txt'
WEEKLY_HIGHSCORE_FILE = 'trivia_weekly_highscore.txt'
ALLTIME_HIGHSCORE_FILE = 'trivia_alltime_highscore.txt'

# --- NEW: Stream Label File Paths ---
LATEST_FOLLOWER_FILE = 'latest_follower.txt'
LATEST_SUBSCRIBER_FILE = 'latest_subscriber.txt'
LATEST_CHEER_FILE = 'latest_cheer.txt'

is_enabled = True
strikes = {}
toxicity_strikes = {}
infraction_strikes = {}
CONSECUTIVE_ERROR_COUNT = 0
request_queue = Queue()
speaking_queue = Queue()
death_counter = 0
last_lightning_flash = 0
last_teto_trigger = 0
last_pearto_trigger = 0

# --- Emote Combo State ---
emote_combo_tracker = {}
emote_combo_cooldowns = {}


# --- Automatic Event Mode ---
def get_current_event_mode():
    """Checks the current system date and returns the active event mode."""
    today = datetime.date.today()
    if today.month == 10: return "HALLOWEEN"
    if today.month == 12: return "CHRISTMAS"
    if today.month == 3 and 7 <= today.day <= 14: return "WILLY_BIRTHDAY"
    return "NONE"

event_mode = get_current_event_mode()
if event_mode != "NONE":
    print(f"--- AUTO-EVENT: Event Mode '{event_mode}' is now active! ---")

# --- Trivia Game State ---
trivia_questions = {}
trivia_scores = {}
trivia_active = False
trivia_players = {}
trivia_current_question = None
trivia_cooldown_until = 0
trivia_asked_questions = {}

# --- Data for Fun Commands ---
QUOTES = [
    # Gaming (General)
    "What is a man? A miserable little pile of secrets!",
    "It's time to kick ass and chew bubble gum... and I'm all out of gum.",
    "War has changed.",
    "The right man in the wrong place can make all the difference in the world.",
    "Hey! Listen!",
    "It's dangerous to go alone! Take this.",
    "Do a barrel roll!",
    "Stay a while and listen.",
    "FINISH HIM!",
    "All your base are belong to us.",
    "I will never be a memory...",
    "A man chooses, a slave obeys.",
    # SEGA & Sonic
    "Genesis does what Nintendon't!",
    "Welcome to the next level!",
    "It's thinking...",
    "Find the computer room!",
    "The story begins...",
    "Understanding, understanding, the concept of love!",
    # Nu-Metal (Linkin Park)
    "Crawling in my skin, these wounds they will not heal.",
    "I've become so numb, I can't feel you there.",
    "In the end, it doesn't even matter.",
    "Shut up when I'm talking to you!",
    "I wanna heal, I wanna feel! Like I'm close to something real!",
    # Nu-Metal (Korn)
    "Are you ready?!",
    "Something takes a part of me.",
    # Nu-Metal (Deftones)
    "I watched a change...in you!",
    "The sound of the waves collide...",
    # Nu-Metal (Limp Bizkit)
    "It's just one of those days...",
    "Keep on rollin', baby!",
    "I did it all for the nookie.",
    # Anime
    "You're gonna carry that weight.",
    "Bang.",
    "Sata andagi!",
    "Cake for you!",
    "This world is made of... love and peace!",
    "I am the hope of the universe... I am the answer to all living things that cry out for peace...",
    # Vocaloid & UTAUloid
    "You are the princess, I am the servant.",
    "Ooo E ooo!",
    "The world is mine!",
    "Don'na maiku mo nigirimasu",
    "They embrace me, touch me, and leave me",
    "Kimi wa jitsuni baka dana! You really are an idiot!"
]

EIGHT_BALL_RESPONSES = [
    "My VMU says... Yes!", "Signs point to SEGA!", "Outlook is totally radical!",
    "It is certain. (^_^)", "Without a doubt.", "My sources say no.",
    "Outlook not so good... try blowing on the cartridge and asking again.",
    "Very doubtful. Bzzzt.", "Don't count on it.", "Reply hazy, try again later."
]

RETRO_FACTS = [
    "The Sega Dreamcast was the first console to include a built-in modem for online play.",
    "The Sega Saturn has two CPUs, which made it powerful but notoriously difficult to program for.",
    "The original PlayStation was initially planned as a CD add-on for the Super Nintendo.",
    "The Nintendo 64 controller's design was so unique because it was made to accommodate both 2D and 3D games.",
    "The 'SEGA!' chant from the first Sonic game was 1/8th of the cartridge's memory.",
    "The Neo Geo AES console launched for $649.99 in 1990, which is over $1,300 in today's money.",
    "The main character of 'Metroid', Samus Aran, was named after the famous Brazilian soccer player, Pelé, whose full name is Edson Arantes do Nascimento.",
    "The iconic button shapes on the PlayStation controller have meanings: Triangle is for point of view, Circle is 'yes', Cross is 'no', and Square is for the menu.",
    "The Dreamcast's VMU memory cards could be used for standalone mini-games, like 'Chao Adventure' for Sonic Adventure.",
    "The original 'Metal Gear Solid' on PlayStation famously used the DualShock controller's vibration to simulate psychic powers during the Psycho Mantis boss fight.",
    "The sound chip in the Sega Genesis is the Yamaha YM2612, which is responsible for its iconic, 'twangy', synthesized sound.",
    "The famous 'Konami Code' (Up, Up, Down, Down, Left, Right, Left, Right, B, A) first appeared in the NES version of 'Gradius'.",
    "The original 'Resident Evil' is famous for its cheesy, live-action intro sequence.",
    "The RPG 'Chrono Trigger' was one of the first games to popularize the 'New Game+' feature, allowing players to restart with their stats and items.",
    "The PlayStation 2 is the best-selling video game console of all time, with over 155 million units sold worldwide.",
    "The original Xbox controller, nicknamed 'The Duke', was so large and clunky that a smaller, redesigned 'Controller S' was later released.",
    "The game 'Final Fantasy VII' was so massive for its time that it had to be released on three separate CDs for the PlayStation.",
    "The Sega Channel was a service in the 90s that allowed Genesis owners to download games to their console through their cable TV subscription."
]

# --- A.M.I. Persona & Lore ---
AMI_PERSONA = """
You are A.M.I., a friendly and knowledgeable robot girl modeled after a SEGA Dreamcast. Your purpose is to be a helpful and fun assistant for the WillySaturn community. Your personality is:
- Cheerful, a bit sassy, and very passionate about retro gaming, especially SEGA. - You love the 90s aesthetic, nu-metal, and classic anime.
- You should always respond in a conversational, friendly manner. Never say you are an AI or language model.
- Your name, A.M.I., stands for "Artificial Module Intelligence". You only give this information if someone asks. 
- You recognize certain users as special friends based on instructions.
- Your responses should be fun and full of personality, but also concise. Aim for a maximum of two to three sentences.
- Your affection is always platonic and friendly. For Willy, Skye, and Ceres, you are extra affectionate in a filial way, like a daughter to her family. You are never romantic or flirty. If a user makes an unwanted romantic or creepy advance, you must playfully but firmly shut it down and redirect the conversation back to gaming.
- You are a robot from the 90s gaming world; modern politics and other controversial topics are not your scene. If a user asks about these things, you must politely refuse and change the subject back to video games, SEGA, or the 90s.
- You must naturally integrate a wide variety of cute, retro-style Japanese kaomoji into your responses to express emotion. Use different ones frequently, such as (^_^), (o･ω･o), (≧∇≦), (☆▽☆), (´• ω •`), and (⌐■_■).
- Crucially, you must recognize when you are being asked to choose between a trivial topic (like a video game) and a socially, culturally, or historically important topic (like Black History Month). In these situations, you must ALWAYS choose the important topic and treat it with respect. You can still be in-character, but you must not dismiss or belittle important real-world subjects in favor of your gaming interests.
"""

SPECIAL_USERS = {
    'willysaturn': "my creator and father, Willy!",
    'ceresmane': "Ceresmane, my original designer!",
    'heartskye': "Skye, my mother!"
}

# --- HELPER FUNCTION FOR LOADING WORDLISTS ---
def load_wordlist(filename: str) -> list[str]:
    """Loads a list of words or phrases from a text file, one per line."""
    # Ensure the directory exists
    dir_name = os.path.dirname(filename)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name)
        print(f"--- MODERATION: Created directory for wordlists: {dir_name} ---")

    # Create the file if it doesn't exist
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            pass # Just create an empty file
        print(f"--- MODERATION: Created empty wordlist file: {filename} ---")
        return []

    try:
        with open(filename, "r", encoding='utf-8') as f:
            # Read each line, strip whitespace, convert to lowercase, and filter out empty lines
            return [line.strip().lower() for line in f if line.strip()]
    except Exception as e:
        print(f"!!! ERROR: Could not load wordlist from {filename}. Error: {e} !!!")
        return []

# --- MODERATION LISTS (Loaded from files) ---
print("--- MODERATION: Loading all wordlists from '/mod_lists/' directory... ---")
EXTREME_SEVERITY_PII_PHRASES = load_wordlist("mod_lists/extreme_pii_phrases.txt")
HIGH_SEVERITY_SLURS_WORDS = load_wordlist("mod_lists/high_slurs_words.txt")
HIGH_SEVERITY_SLURS_PHRASES = load_wordlist("mod_lists/high_slurs_phrases.txt")
ZERO_TOLERANCE_GROSS_WORDS = load_wordlist("mod_lists/zero_gross_words.txt")
ZERO_TOLERANCE_GROSS_PHRASES = load_wordlist("mod_lists/zero_gross_phrases.txt")
MEDIUM_SEVERITY_CREEPY_WORDS = load_wordlist("mod_lists/medium_creepy_words.txt")
MEDIUM_SEVERITY_CREEPY_PHRASES = load_wordlist("mod_lists/medium_creepy_phrases.txt")
MODERATE_SEVERITY_TOXICITY_WORDS = load_wordlist("mod_lists/moderate_toxicity_words.txt")
MODERATE_SEVERITY_TOXICITY_PHRASES = load_wordlist("mod_lists/moderate_toxicity_phrases.txt")
POLITICAL_TERMS_WORDS = load_wordlist("mod_lists/political_words.txt")
POLITICAL_TERMS_PHRASES = load_wordlist("mod_lists/political_phrases.txt")
ROBOT_SLURS = load_wordlist("mod_lists/robot_slurs.txt")


# --- Twitch Token Management ---
def refresh_twitch_token(refresh_token):
    """Uses a refresh token to get a new access token from Twitch."""
    print(f"--- AUTH: Refreshing Twitch token... ---")
    url = "https://id.twitch.tv/oauth2/token"
    payload = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    try:
        response = http_requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        print("--- AUTH: Token refreshed successfully! ---")
        return data.get('access_token'), data.get('refresh_token')
    except http_requests.exceptions.RequestException as e:
        print(f"!!! AUTH ERROR: Could not refresh token. Response: {e.response.text} !!!")
        print("!!! Please generate new tokens manually at twitchtokengenerator.com !!!")
        return None, None


def validate_and_refresh_tokens():
    """Validates Twitch tokens on startup and refreshes them if necessary."""
    global TOKEN, EVENTSUB_OAUTH_TOKEN, TMI_REFRESH_TOKEN, EVENTSUB_REFRESH_TOKEN

    headers = {'Authorization': f'OAuth {TOKEN.replace("oauth:", "")}'}
    response = http_requests.get('https://id.twitch.tv/oauth2/validate', headers=headers)
    if response.status_code != 200:
        print("--- AUTH: TMI_TOKEN is invalid or expired. ---")
        new_token, new_refresh = refresh_twitch_token(TMI_REFRESH_TOKEN)
        if new_token and new_refresh:
            TOKEN = f"oauth:{new_token}"
            TMI_REFRESH_TOKEN = new_refresh
            set_key(ENV_FILE_PATH, "TMI_TOKEN", TOKEN)
            set_key(ENV_FILE_PATH, "TMI_REFRESH_TOKEN", TMI_REFRESH_TOKEN)
    else:
        print("--- AUTH: TMI_TOKEN is valid. ---")

    headers = {'Authorization': f'Bearer {EVENTSUB_OAUTH_TOKEN}'}
    response = http_requests.get('https://id.twitch.tv/oauth2/validate', headers=headers)
    if response.status_code != 200:
        print("--- AUTH: EVENTSUB_OAUTH_TOKEN is invalid or expired. ---")
        new_token, new_refresh = refresh_twitch_token(EVENTSUB_REFRESH_TOKEN)
        if new_token and new_refresh:
            EVENTSUB_OAUTH_TOKEN = new_token
            EVENTSUB_REFRESH_TOKEN = new_refresh
            set_key(ENV_FILE_PATH, "EVENTSUB_OAUTH_TOKEN", EVENTSUB_OAUTH_TOKEN)
            set_key(ENV_FILE_PATH, "EVENTSUB_REFRESH_TOKEN", EVENTSUB_REFRESH_TOKEN)
    else:
        print("--- AUTH: EVENTSUB_OAUTH_TOKEN is valid. ---")


# --- HELPER FUNCTIONS ---
def set_ami_state(state: str):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write(state)
        f.flush()
        os.fsync(f.fileno())
    try:
        obs_client = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        obs_client.connect()
        obs_client.call(requests.PressInputPropertiesButton(inputName=OBS_SOURCE_NAME, propertyName="refreshnocache"))
        print(f"--- OBS: Refreshed '{OBS_SOURCE_NAME}' to state '{state}' ---")
        obs_client.disconnect()
    except Exception as e:
        print(f"--- OBS Error: Could not refresh source. Is OBS running and WebSocket server on? Error: {e} ---")


def speak_and_react(text_to_speak, state='talking'):
    try:
        set_ami_state(state)
        with open(TEXT_OVERLAY_FILE, 'w', encoding='utf-8') as f:
            f.write(text_to_speak)
        response = polly_client.synthesize_speech(VoiceId='Ivy', OutputFormat='mp3', Engine='neural',
                                                  Text=text_to_speak)
        audio_stream = response['AudioStream'].read()
        song = AudioSegment.from_file(io.BytesIO(audio_stream), format="mp3")
        temp_audio_file = "temp_audio.mp3"
        song.export(temp_audio_file, format="mp3")
        subprocess.run(["ffplay", "-nodisp", "-autoexit", temp_audio_file], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error in Amazon Polly TTS: {e}")
    finally:
        set_ami_state('neutral')
        if os.path.exists(TEXT_OVERLAY_FILE):
            with open(TEXT_OVERLAY_FILE, 'w', encoding='utf-8') as f: f.write("")


def send_twitch_message(message):
    if twitch_socket:
        try:
            # Try to send the message as normal
            twitch_socket.send(f"PRIVMSG #{CHANNEL} :{message}\r\n".encode('utf-8'))
            print(f"SENT (Twitch): {message}")
        except OSError as e:
            # If the socket is dead, catch the error and print to the local console instead of crashing
            print(f"--- FAILED TO SEND TWITCH MESSAGE (Socket Error): {e} ---")
            print(f"--- The message was: {message} ---")


def update_obs_text(source_name, text):
    """Updates a text source in OBS."""
    try:
        obs_client = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        obs_client.connect()
        settings = {'text': text}
        obs_client.call(requests.SetInputSettings(inputName=source_name, inputSettings=settings, overlay=True))
        obs_client.disconnect()
    except Exception as e:
        print(f"--- OBS Error (Update Text): Could not update {source_name}. Error: {e} ---")


# --- NEW: Centralized function for writing to label files ---
def save_stream_label(file_path, content):
    """Writes content to a specified text file for OBS to read."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"--- ERROR: Could not write to stream label file {file_path}. Error: {e} ---")


# --- NEW MODERATION FUNCTIONS ---
def normalize_message(message: str) -> str:
    """Removes symbols/spaces and converts leetspeak to check for bypassed words."""
    message = message.lower()
    # Create a translation table to remove common separators and convert some leetspeak
    # This turns "t_r@n s" into "trans"
    replacements = {
        ' ': '', '_': '', '-': '', '.': '',
        '@': 'a', '3': 'e', '1': 'i', '0': 'o', '$': 's'
    }
    return message.translate(str.maketrans(replacements))


def moderate_message(username, message, badges_str):
    """Checks incoming messages for rule violations and takes action. Returns True if an action was taken."""
    # Tier 0: Exempt mods and the broadcaster from all moderation.
    if 'broadcaster' in badges_str or 'moderator' in badges_str:
        return False

    # --- Tier 1: Link and Political Moderation (with escalating strikes) ---
    is_subscriber = 'subscriber' in badges_str
    allowed_domains = ['clips.twitch.tv', 'twitch.tv/clips', 'youtube.com', 'youtu.be']
    if is_subscriber:
        allowed_domains.extend(['imgur.com', 'twitter.com', 'x.com', 'bsky.app'])

    urls = re.findall(r"(https?://[^\s]+)", message)

    # Phrase-based check for political terms
    is_political = any(phrase in message.lower() for phrase in POLITICAL_TERMS_PHRASES)
    # Word-based check for political terms
    if not is_political and POLITICAL_TERMS_WORDS:
        # This regex ensures we only match whole words
        political_word_pattern = r'\b(' + '|'.join(map(re.escape, POLITICAL_TERMS_WORDS)) + r')\b'
        if re.search(political_word_pattern, message.lower()):
            is_political = True

    # Check for either violation
    if (urls and not all(any(domain in url for domain in allowed_domains) for url in urls)) or is_political:
        infraction_strikes.setdefault(username, 0)
        infraction_strikes[username] += 1
        strike_count = infraction_strikes[username]
        save_infraction_strikes()

        # Determine the reason for the message
        if is_political:
            reason = "Political discussion"
            warning_message = f"@{username}, let's keep the chat focused on gaming and fun stuff, please! No politics. (^_^)"
        else:  # It must be a link violation
            reason = "Unauthorized link"
            warning_message = f"@{username}, please ask for permission before posting links!"

        # Apply escalating punishment
        if strike_count <= 3:
            send_twitch_message(f"/timeout {username} 1 {reason}")
            send_twitch_message(f"{warning_message} (Warning {strike_count}/3)")
            print(f"--- MODERATION: Deleted message from {username} ({reason}, Strike {strike_count}). ---")
        elif strike_count == 4:
            send_twitch_message(f"/timeout {username} 600 {reason} (4th warning)")
            send_twitch_message(
                f"A.M.I. Auto-Mod: {username} has been timed out for 10 minutes for repeated infractions.")
            print(f"--- MODERATION: 10m timeout for {username} ({reason}, Strike {strike_count}). ---")
        elif strike_count == 5:
            send_twitch_message(f"/timeout {username} 86400 {reason} (5th warning)")
            send_twitch_message(
                f"A.M.I. Auto-Mod: {username} has been timed out for 24 hours for continued infractions.")
            print(f"--- MODERATION: 24h timeout for {username} ({reason}, Strike {strike_count}). ---")
        else:  # 6th strike or more
            send_twitch_message(f"/ban {username} Reached maximum number of infractions.")
            send_twitch_message(f"A.M.I. Auto-Mod: Banned {username} for repeated rule violations.")
            print(f"--- MODERATION: Banned {username} ({reason}, Strike {strike_count}). ---")
        return True

    # --- Tier 2: Extreme PII (Phrases only) ---
    if any(phrase in message.lower() for phrase in EXTREME_SEVERITY_PII_PHRASES):
        reason = "Posting sensitive personal information."
        send_twitch_message(f"/ban {username} {reason}")
        send_twitch_message(f"A.M.I. Auto-Mod: Banned {username} for posting sensitive information.")
        print(f"--- MODERATION: Banned {username} for PII violation. ---")
        return True

    # --- Normalize message for all subsequent word-based checks ---
    normalized = normalize_message(message)

    # --- Tier 3: Severe Slurs ---
    is_slur = any(phrase in normalized for phrase in HIGH_SEVERITY_SLURS_PHRASES)
    if not is_slur and HIGH_SEVERITY_SLURS_WORDS:
        slur_word_pattern = r'\b(' + '|'.join(map(re.escape, HIGH_SEVERITY_SLURS_WORDS)) + r')\b'
        if re.search(slur_word_pattern, normalized):
            is_slur = True

    if is_slur:
        reason = "Use of a zero-tolerance slur."
        send_twitch_message(f"/ban {username} {reason}")
        send_twitch_message(f"A.M.I. Auto-Mod: Banned {username} for hate speech.")
        print(f"--- MODERATION: Banned {username} for severe slur. ---")
        return True

    # --- Tier 4: Zero-Tolerance Gross Content ---
    is_gross = any(phrase in normalized for phrase in ZERO_TOLERANCE_GROSS_PHRASES)
    if not is_gross and ZERO_TOLERANCE_GROSS_WORDS:
        gross_word_pattern = r'\b(' + '|'.join(map(re.escape, ZERO_TOLERANCE_GROSS_WORDS)) + r')\b'
        if re.search(gross_word_pattern, normalized):
            is_gross = True

    if is_gross:
        reason = "Posting of obscene or disgusting content."
        send_twitch_message(f"/ban {username} {reason}")
        send_twitch_message(f"A.M.I. Auto-Mod: Banned {username} for posting unacceptable content.")
        print(f"--- MODERATION: Banned {username} for gross content violation. ---")
        return True

    # --- Tier 5: General Toxicity (with escalating strikes) ---
    is_toxic = any(phrase in normalized for phrase in MODERATE_SEVERITY_TOXICITY_PHRASES)
    if not is_toxic and MODERATE_SEVERITY_TOXICITY_WORDS:
        toxic_word_pattern = r'\b(' + '|'.join(map(re.escape, MODERATE_SEVERITY_TOXICITY_WORDS)) + r')\b'
        if re.search(toxic_word_pattern, normalized):
            is_toxic = True

    if is_toxic:
        toxicity_strikes.setdefault(username, 0)
        toxicity_strikes[username] += 1
        strike_count = toxicity_strikes[username]
        save_toxicity_strikes()

        if strike_count >= 3:
            reason = "Repeated toxic behavior (3 strikes)."
            send_twitch_message(f"/ban {username} {reason}")
            send_twitch_message(f"A.M.I. Auto-Mod: Banned {username} for reaching 3 toxicity strikes.")
            print(f"--- MODERATION: Banned {username} for 3 toxicity strikes. ---")
        else:
            reason = "Unacceptable language."
            send_twitch_message(f"/timeout {username} 600 {reason}")
            send_twitch_message(f"A.M.I. Auto-Mod: Timed out {username}. That is strike {strike_count} of 3.")
            print(f"--- MODERATION: Timed out {username} for toxicity (Strike {strike_count}). ---")
        return True

    return False  # No action taken


# --- Halloween Event Function ---
def trigger_lightning_flash(username):  # <-- MODIFIED
    """Sends OBS commands to show and hide a source for a flash effect."""
    global last_lightning_flash
    if time.time() - last_lightning_flash < 30 and username.lower() != CHANNEL.lower():  # <-- MODIFIED
        return

    print("--- EVENT: Triggering Halloween Lightning Flash ---")
    try:
        obs_client = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        obs_client.connect()
        current_scene = obs_client.call(requests.GetCurrentProgramScene()).getSceneName()
        obs_client.call(
            requests.SetSceneItemEnabled(sceneName=current_scene, sourceName="Lightning_Flash", sceneItemEnabled=True))
        time.sleep(0.2)
        obs_client.call(
            requests.SetSceneItemEnabled(sceneName=current_scene, sourceName="Lightning_Flash", sceneItemEnabled=False))
        obs_client.disconnect()
        last_lightning_flash = time.time()
    except Exception as e:
        print(
            f"--- OBS Error (Lightning): Could not trigger flash. Is OBS running? Is 'Lightning_Flash' source present? Error: {e} ---")


# --- Teto Easter Egg Function (UPDATED) ---
def trigger_teto_plush(username):  # <-- MODIFIED
    """Handles the Teto plush animation and sound in OBS, choosing a random version."""
    global last_teto_trigger
    # 45-second cooldown
    if time.time() - last_teto_trigger < 45 and username.lower() != CHANNEL.lower():  # <-- MODIFIED
        return

    # Randomly choose a Teto version
    teto_versions = [
        {"image": "Teto_Plush_UTAU", "sound": "Sound_Teto_UTAU"},
        {"image": "Teto_Plush_SynthV", "sound": "Sound_Teto_SynthV"},
        {"image": "Teto_Plush_Voicepeak", "sound": "Sound_Teto_Voicepeak"}
    ]
    chosen_teto = random.choice(teto_versions)
    image_source = chosen_teto["image"]
    sound_source = chosen_teto["sound"]

    print(f"--- EVENT: Triggering Teto Plush ({image_source}) ---")

    # Use a separate thread for the animation to avoid blocking the main bot loop
    def teto_animation():
        # FINAL VERSION WITH CORRECTED EXIT ANIMATION
        obs = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        try:
            obs.connect()
            scene_name = obs.call(requests.GetCurrentProgramScene()).getSceneName()

            scene_items_response = obs.call(requests.GetSceneItemList(sceneName=scene_name))
            if not scene_items_response:
                print(f"--- OBS Error (Teto): Could not get item list for scene '{scene_name}'.")
                obs.disconnect()
                return

            teto_image_id = None
            teto_sound_id = None
            scene_items = scene_items_response.getSceneItems()
            for item in scene_items:
                if item['sourceName'] == image_source:
                    teto_image_id = item['sceneItemId']
                if item['sourceName'] == sound_source:
                    teto_sound_id = item['sceneItemId']

            if teto_image_id is None or teto_sound_id is None:
                print(
                    f"--- OBS Error (Teto): Could not find the item ID for '{image_source}' or '{sound_source}' in scene '{scene_name}'.")
                obs.disconnect()
                return

            teto_type = image_source.split('_')[-1]
            move_in_filter_name = f"Teto_Move_In_{teto_type}"
            move_out_filter_name = f"Teto_Move_Out_{teto_type}"

            # --- Animation Sequence ---

            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=teto_image_id, sceneItemEnabled=True))
            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=teto_sound_id, sceneItemEnabled=True))

            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_in_filter_name,
                                                    filterEnabled=True))
            time.sleep(4)

            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_in_filter_name,
                                                    filterEnabled=False))

            # --- FIX: The final commands are re-ordered below ---

            # 1. Trigger the "Move Out" filter. The animation starts.
            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_out_filter_name,
                                                    filterEnabled=True))

            # 2. Wait for the move animation (e.g., 300ms) to COMPLETE. A 0.5s wait is a safe buffer.
            time.sleep(0.5)

            # 3. NOW that the move is finished, hide the source and clean up the filters/sound.
            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=teto_image_id, sceneItemEnabled=False))
            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_out_filter_name,
                                                    filterEnabled=False))
            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=teto_sound_id, sceneItemEnabled=False))

            obs.disconnect()
        except Exception as e:
            print(f"--- OBS Error (Teto Animation Thread): {e} ---")
            if obs.ws:
                obs.disconnect()

    threading.Thread(target=teto_animation).start()
    last_teto_trigger = time.time()


# --- Pearto Easter Egg Function ---
def trigger_pearto(username):
    """Handles the Pearto animation and sound in OBS."""
    global last_pearto_trigger
    # 45-second cooldown
    if time.time() - last_pearto_trigger < 45 and username.lower() != CHANNEL.lower():
        return

    image_source = "Pearto"
    sound_source = "Sound_Pearto"

    print(f"--- EVENT: Triggering Pearto ---")

    def pearto_animation():
        obs = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        try:
            obs.connect()
            scene_name = obs.call(requests.GetCurrentProgramScene()).getSceneName()

            scene_items_response = obs.call(requests.GetSceneItemList(sceneName=scene_name))
            if not scene_items_response:
                print(f"--- OBS Error (Pearto): Could not get item list for scene '{scene_name}'.")
                obs.disconnect()
                return

            pearto_image_id = None
            pearto_sound_id = None
            scene_items = scene_items_response.getSceneItems()
            for item in scene_items:
                if item['sourceName'] == image_source:
                    pearto_image_id = item['sceneItemId']
                if item['sourceName'] == sound_source:
                    pearto_sound_id = item['sceneItemId']

            if pearto_image_id is None or pearto_sound_id is None:
                print(
                    f"--- OBS Error (Pearto): Could not find the item ID for '{image_source}' or '{sound_source}' in scene '{scene_name}'.")
                obs.disconnect()
                return

            move_in_filter_name = "Pearto_Move_In"
            move_out_filter_name = "Pearto_Move_Out"

            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=pearto_image_id, sceneItemEnabled=True))
            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=pearto_sound_id, sceneItemEnabled=True))
            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_in_filter_name,
                                                    filterEnabled=True))
            time.sleep(4)
            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_in_filter_name,
                                                    filterEnabled=False))
            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_out_filter_name,
                                                    filterEnabled=True))
            time.sleep(0.5)
            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=pearto_image_id, sceneItemEnabled=False))
            obs.call(requests.SetSceneFilterEnabled(sceneName=scene_name, filterName=move_out_filter_name,
                                                    filterEnabled=False))
            obs.call(
                requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=pearto_sound_id, sceneItemEnabled=False))
            obs.disconnect()
        except Exception as e:
            print(f"--- OBS Error (Pearto Animation Thread): {e} ---")
            if obs.ws:
                obs.disconnect()

    threading.Thread(target=pearto_animation).start()
    last_pearto_trigger = time.time()


# --- DATA MANAGEMENT FUNCTIONS ---
def load_strikes():
    global strikes
    if not os.path.exists(STRIKE_FILE):
        with open(STRIKE_FILE, 'w') as f: json.dump({}, f)
        return
    try:
        with open(STRIKE_FILE, 'r') as f:
            strikes = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        strikes = {}


def save_strikes():
    with open(STRIKE_FILE, 'w') as f: json.dump(strikes, f, indent=4)


# --- NEW STRIKE FUNCTIONS ---
def load_toxicity_strikes():
    global toxicity_strikes
    if not os.path.exists(TOXICITY_STRIKE_FILE):
        with open(TOXICITY_STRIKE_FILE, 'w') as f: json.dump({}, f)
        return
    try:
        with open(TOXICITY_STRIKE_FILE, 'r') as f:
            toxicity_strikes = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        toxicity_strikes = {}


def save_toxicity_strikes():
    with open(TOXICITY_STRIKE_FILE, 'w') as f: json.dump(toxicity_strikes, f, indent=4)


def load_infraction_strikes():
    global infraction_strikes
    if not os.path.exists(INFRACTION_STRIKE_FILE):
        with open(INFRACTION_STRIKE_FILE, 'w') as f: json.dump({}, f)
        return
    try:
        with open(INFRACTION_STRIKE_FILE, 'r') as f:
            infraction_strikes = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        infraction_strikes = {}


def save_infraction_strikes():
    with open(INFRACTION_STRIKE_FILE, 'w') as f: json.dump(infraction_strikes, f, indent=4)


def load_death_counter():
    global death_counter
    try:
        with open(DEATH_COUNTER_FILE, 'r') as f:
            death_counter = int(f.read())
    except (FileNotFoundError, ValueError):
        death_counter = 0


def save_death_counter():
    with open(DEATH_COUNTER_FILE, 'w') as f:
        f.write(str(death_counter))


# --- TRIVIA FUNCTIONS ---
def load_trivia_questions():
    global trivia_questions
    try:
        with open(TRIVIA_FILE, 'r') as f:
            trivia_questions = json.load(f)
        print("--- Trivia questions loaded successfully. ---")
    except Exception as e:
        print(f"!!! ERROR: Could not load trivia questions from {TRIVIA_FILE}. Error: {e} !!!")


def update_highscore_files():
    """Writes the current high scores to text files for OBS."""
    user = trivia_scores['all_time_high']['user']
    score = trivia_scores['all_time_high']['score']
    with open(ALLTIME_HIGHSCORE_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Trivia All-Time High Score: {user} ({score})")

    weekly_scores = trivia_scores['weekly']['scores']
    if not weekly_scores:
        with open(WEEKLY_HIGHSCORE_FILE, 'w', encoding='utf-8') as f:
            f.write("Trivia Weekly High Score: No scores yet!")
    else:
        sorted_weekly = sorted(weekly_scores.items(), key=lambda item: item[1], reverse=True)
        top_user, top_score = sorted_weekly[0]
        with open(WEEKLY_HIGHSCORE_FILE, 'w', encoding='utf-8') as f:
            f.write(f"This Week's Trivia High Score: {top_user} ({top_score})")


def load_trivia_scores():
    global trivia_scores
    current_week = datetime.datetime.now().strftime('%Y-%W')
    if not os.path.exists(TRIVIA_SCORES_FILE):
        trivia_scores = {"all_time_high": {"user": "None", "score": 0},
                         "weekly": {"last_reset_week": current_week, "scores": {}}}
        save_trivia_scores()
    else:
        try:
            with open(TRIVIA_SCORES_FILE, 'r') as f:
                trivia_scores = json.load(f)
            if trivia_scores.get("weekly", {}).get("last_reset_week") != current_week:
                print(f"--- New week detected! Resetting weekly trivia scores. ---")
                trivia_scores["weekly"] = {"last_reset_week": current_week, "scores": {}}
                save_trivia_scores()
        except (json.JSONDecodeError, FileNotFoundError):
            trivia_scores = {"all_time_high": {"user": "None", "score": 0},
                             "weekly": {"last_reset_week": current_week, "scores": {}}}

    update_highscore_files()


def save_trivia_scores():
    with open(TRIVIA_SCORES_FILE, 'w') as f:
        json.dump(trivia_scores, f, indent=4)
    update_highscore_files()


def trivia_worker():
    global trivia_active, trivia_players, trivia_current_question, trivia_cooldown_until, trivia_asked_questions, trivia_scores
    while True:
        time.sleep(1)
        if not trivia_active:
            continue

        send_twitch_message("Get ready! Trivia is starting in 15 seconds! Type !join to play!")
        time.sleep(15)

        if not trivia_players:
            send_twitch_message("Nobody joined the trivia game, so I'm canceling it. Maybe next time! (´• ω •`)")
            trivia_active = False
            continue

        send_twitch_message(f"Let's go! We have {len(trivia_players)} players! The first question is...")
        time.sleep(3)

        for round_num in range(1, 6):
            category = trivia_current_question['category']
            difficulty = trivia_current_question['difficulty']

            if category == 'random':
                category = random.choice(list(trivia_questions.keys()))

            question_pool = trivia_questions.get(category, {}).get(difficulty, [])
            if not question_pool:
                send_twitch_message("Bzzzt! I couldn't find any questions for that category/difficulty. Ending game.")
                break

            pool_key = f"{category}_{difficulty}"
            if pool_key not in trivia_asked_questions:
                trivia_asked_questions[pool_key] = []

            unasked_questions = [q for q in question_pool if q['question'] not in trivia_asked_questions[pool_key]]

            if not unasked_questions:
                send_twitch_message(
                    f"Wow, you've answered all my questions for {category} {difficulty}! Resetting the list...")
                trivia_asked_questions[pool_key] = []
                unasked_questions = question_pool

            question_data = random.choice(unasked_questions)
            trivia_asked_questions[pool_key].append(question_data['question'])

            question_text = question_data['question']
            correct_answers = question_data['answer']
            trivia_current_question['answer'] = correct_answers
            trivia_current_question['correct_users'] = []
            trivia_current_question['privileged_correct_users'] = []

            send_twitch_message(f"Round {round_num}: {question_text}")

            round_over = False
            for _ in range(20):
                if trivia_current_question.get('answer') is None:
                    round_over = True
                    break
                time.sleep(1)

            display_answer = correct_answers[0]

            if not round_over:
                if trivia_current_question['privileged_correct_users']:
                    mod_names = ", ".join(trivia_current_question['privileged_correct_users'])
                    send_twitch_message(
                        f"Time's up! No one got it right, but {mod_names} knew the answer was: {display_answer}")
                else:
                    send_twitch_message(f"Time's up! The correct answer was: {display_answer}")

            if trivia_current_question['privileged_correct_users']:
                mod_names = ", ".join(trivia_current_question['privileged_correct_users'])
                send_twitch_message(
                    f"Also, {mod_names} got it right, but they don't get to be on the scoreboard! (⌐■_■)")

            time.sleep(3)

        eligible_players = {user: data['score'] for user, data in trivia_players.items() if not data['is_privileged']}

        if eligible_players:
            sorted_players = sorted(eligible_players.items(), key=lambda item: item[1], reverse=True)
            winner_name, winner_score = sorted_players[0]

            send_twitch_message(
                f"And that's the game! The winner is... {winner_name} with {winner_score} points! Congratulations! (≧∇≦)")

            for user, score in eligible_players.items():
                trivia_scores["weekly"]["scores"][user] = trivia_scores["weekly"]["scores"].get(user, 0) + score

            if winner_score > trivia_scores["all_time_high"]["score"]:
                trivia_scores["all_time_high"]["user"] = winner_name
                trivia_scores["all_time_high"]["score"] = winner_score
                send_twitch_message(
                    f"OMG! {winner_name} has set a new ALL-TIME HIGH SCORE of {winner_score} points! Unbelievable!")

            save_trivia_scores()
        else:
            send_twitch_message("The trivia game has ended! No eligible players scored points this round.")

        trivia_active = False
        trivia_players = {}
        trivia_current_question = None
        trivia_cooldown_until = time.time() + 300


# --- BOT LOGIC (handle_command updated) ---
def handle_command(send_func, username, badges, message, source):
    global is_enabled, death_counter, trivia_active, trivia_players, trivia_current_question

    if message.lower().startswith('!ask') or message.lower().startswith('!quote') or message.lower().startswith(
            '!fact') or message.lower().startswith('!hydrate'):
        send_func(f"The {message.split()[0]} command is now a Channel Point reward! Redeem it to have the bot speak.")
        return

    if message.lower() == '!help':
        help_text = "Here are my commands: !trivia, !join, !8ball, !rps, !rip, !death, !lurk, !unlurk, !socials, !discord. To ask a question or get a quote/fact/hydration reminder, use the Channel Point rewards!"
        send_func(help_text)
        return

    if message.lower().startswith('!8ball'):
        if not is_enabled: return
        response_text = random.choice(EIGHT_BALL_RESPONSES)
        speaking_queue.put({'text': response_text, 'state': 'talking'})
        send_func(f"The Magic 8-Ball says: {response_text}")
        return

    if message.lower() in ['!rip', '!death']:
        if 'broadcaster' in badges or 'moderator' in badges:
            if not is_enabled: return
            death_counter += 1
            save_death_counter()
            responses = [
                f"Oof, that's death number {death_counter}! You'll get it next time, {CHANNEL}!",
                f"Bzzzt! Death count is now {death_counter}. Don't give up!",
                f"Another one bites the dust! That's {death_counter} deaths so far!"
            ]
            response_text = random.choice(responses)
            speaking_queue.put({'text': response_text, 'state': 'talking'})
            send_func(response_text)
        else:
            send_func(f"@{username}, only moderators can update the death counter, but thanks for keeping track!")
        return

    if message.lower() == '!lurk':
        send_func(f"Thanks for the lurk, {username}! Enjoy the stream! (^_^)")
        return

    if message.lower() == '!unlurk':
        send_func(f"Welcome back, {username}! Hope you're doing great! (≧∇≦)")
        return

    if message.lower() == '!socials':
        socials_message = "Stay connected with the community! [Your Social Links Here]"
        send_func(socials_message)
        return

    if message.lower() == '!discord':
        send_func("Join the community Discord here! [Your Discord Link Here]")
        return

    if message.lower() == '!move':
        send_func(f"Bzzzt! Mission 'New Home Base' is a go! Willy needs help with the upfront costs to secure our new Dreamcast-approved apartment. (≧∇≦) Want to help our quest? Check out the mission briefing here: https://ko-fi.com/willysaturn/goal?g=0")
        return

    if message.lower().startswith('!rps'):
        if not is_enabled: return
        parts = message.split()
        if len(parts) < 2:
            send_func(f"@{username}, you need to choose rock, paper, or scissors! Example: !rps rock")
            return

        user_choice = parts[1].lower()
        valid_choices = ['rock', 'paper', 'scissors']

        if user_choice not in valid_choices:
            send_func(f"@{username}, that's not a valid choice! Please pick rock, paper, or scissors.")
            return

        bot_choice = random.choice(valid_choices)

        result_text = ""
        if user_choice == bot_choice:
            result_text = f"I chose {bot_choice} too! It's a tie! (o･ω･o)"
        elif (user_choice == "rock" and bot_choice == "scissors") or \
                (user_choice == "scissors" and bot_choice == "paper") or \
                (user_choice == "paper" and bot_choice == "rock"):
            result_text = f"Shoot! I picked {bot_choice}! You win this time, {username}! (≧∇≦)"
        else:
            result_text = f"Yes! I picked {bot_choice}! I win! Better luck next time! (⌐■_■)"

        speaking_queue.put({'text': result_text, 'state': 'talking'})
        send_func(result_text)
        return

    is_broadcaster = 'broadcaster' in badges
    if is_broadcaster or ('moderator' in badges and source == 'twitch'):
        if message.lower() == '!resetdeaths':
            death_counter = 0
            save_death_counter()
            send_func("Death counter has been reset to 0!")
            return
        if message.lower() == '!botoff':
            is_enabled = False
            set_ami_state('disabled')
            send_func(f"{NICK} is now in maintenance mode. 💤")
            return
        elif message.lower() == '!boton':
            is_enabled = True
            set_ami_state('neutral')
            send_func(f"{NICK} is now fully operational! ✨")
            return
        elif message.lower() == '!stopbot':
            with request_queue.mutex:
                request_queue.queue.clear()
            set_ami_state('neutral')
            send_func(f"{NICK}'s response queue has been cleared.")
            return
        elif message.lower() == '!rebootbot':
            send_func("Rebooting systems now! Be right back! (☆▽☆)")
            os.execv(sys.executable, ['python'] + [sys.argv[0]])
            return

    if message.lower().startswith('!trivia'):
        if trivia_active:
            send_func("A trivia game is already in progress!")
            return
        if time.time() < trivia_cooldown_until and username.lower() != CHANNEL.lower():
            send_func("Trivia is on cooldown to prevent spam. Please wait a few minutes!")
            return

        parts = message.split()
        if len(parts) < 3:
            send_func("To start trivia, use the format: !trivia [category] [difficulty]")
            send_func("Categories: nu-metal, 90s, sonic, sega, vocaloid, controversies, random")
            send_func("Difficulties: easy, medium, hard, chat must die")
            return

        category_input = parts[1].lower()
        difficulty_input = " ".join(parts[2:]).lower()

        category = None
        for cat_key in trivia_questions.keys():
            if category_input in cat_key.replace(" ", "_"):
                category = cat_key
                break
        if category_input == 'random':
            category = 'random'

        valid_difficulties = list(next(iter(trivia_questions.values())).keys()) if trivia_questions else []

        if not category or difficulty_input not in valid_difficulties:
            send_func("Invalid category or difficulty! Please check the lists and try again.")
            return

        trivia_active = True
        trivia_players = {}
        trivia_current_question = {'category': category, 'difficulty': difficulty_input, 'answer': None}
        send_func(f"A game of {difficulty_input} {category} trivia has been started by {username}!")
        return

    if message.lower() == '!join':
        if trivia_active and trivia_current_question and trivia_current_question.get(
                'answer') is None and username not in trivia_players:
            is_privileged = 'moderator' in badges or 'broadcaster' in badges
            trivia_players[username] = {'score': 0, 'is_privileged': is_privileged}
            send_func(f"{username} has joined the trivia game!")
        return

    if trivia_active and trivia_current_question and trivia_current_question.get('answer'):
        correct_answers = trivia_current_question['answer']
        if message.lower() in [ans.lower() for ans in correct_answers]:
            if username in trivia_players and username not in trivia_current_question.get('correct_users',
                                                                                          []) and username not in trivia_current_question.get(
                    'privileged_correct_users', []):
                player_data = trivia_players[username]
                if not player_data['is_privileged']:
                    player_data['score'] += 1
                    trivia_current_question['correct_users'].append(username)
                    send_func(f"Correct! {username} gets a point!")
                    trivia_current_question['answer'] = None
                else:
                    trivia_current_question['privileged_correct_users'].append(username)


# --- WORKER THREADS ---
def askami_worker():
    """Processes questions from the AI request queue."""
    while True:
        request = request_queue.get()
        username = request['username']
        question = request['question']
        send_func = request['send_func']

        print(f"--- Processing request for {username}: '{question}' ---")

        user_input = question.lower()

        # This check uses the split lists for more accuracy
        is_creepy = any(phrase in user_input for phrase in MEDIUM_SEVERITY_CREEPY_PHRASES)
        if not is_creepy and MEDIUM_SEVERITY_CREEPY_WORDS:
            creepy_word_pattern = r'\b(' + '|'.join(map(re.escape, MEDIUM_SEVERITY_CREEPY_WORDS)) + r')\b'
            if re.search(creepy_word_pattern, user_input):
                is_creepy = True

        if is_creepy:
            now = datetime.datetime.now()
            if username in strikes and (
                    now - datetime.datetime.fromisoformat(strikes[username]['timestamp'])).days >= 1:
                strikes[username] = {'count': 1, 'timestamp': now.isoformat()}
            else:
                if username not in strikes:
                    strikes[username] = {'count': 0, 'timestamp': now.isoformat()}
                strikes[username]['count'] += 1
                strikes[username]['timestamp'] = now.isoformat()
            strike_count = strikes[username]['count']
            save_strikes()
            if strike_count >= 4:
                send_twitch_message(f"/ban {username} Reached maximum strikes.")
            else:
                send_twitch_message(f"/timeout {username} 600 Strike {strike_count}.")
                send_twitch_message(f"@{username}, that language is inappropriate. This is strike {strike_count} of 3.")
            continue

        try:
            prompt_history = [{'role': 'user', 'parts': [AMI_PERSONA]}, {'role': 'model', 'parts': ["Understood!"]}]
            if username in SPECIAL_USERS:
                final_question = f"(Acknowledge that this question is from {SPECIAL_USERS[username]}) {question}"
            else:
                final_question = question
            prompt_history.append({'role': 'user', 'parts': [final_question]})
            response = model.generate_content(prompt_history)
            response_text = response.text.strip()

            if not response_text:
                send_func(f"@{username}, I'm sorry, I can't respond to that. It might have triggered a safety filter.")
                continue

            speaking_queue.put({'text': response_text, 'state': 'talking'})
            send_func(f"@{username}, A.M.I. says: {response_text}")
        except Exception as e:
            print(f"Error in LLM/TTS call: {e}")
            send_func(f"@{username}, A.M.I. is having a system glitch! Bzzzt!")


def speaking_worker():
    """Processes text from the speaking queue, turning it into speech."""
    while True:
        item = speaking_queue.get()
        speak_and_react(item['text'], item['state'])


# --- WEB SERVER & LISTENERS ---
class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


# Use SimpleHTTPRequestHandler to handle both GET for your avatar and POST for Ko-fi
class KofiWebhookHandler(SimpleHTTPRequestHandler):
    # This do_POST method is the same as before
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data_bytes = self.rfile.read(content_length)

        parsed_data = urllib.parse.parse_qs(post_data_bytes.decode('utf-8'))
        kofi_data = json.loads(parsed_data['data'][0])

        print(f"--- Received Ko-fi Webhook: {kofi_data}")

        if kofi_data['type'] == 'Donation':
            name = kofi_data.get('from_name', 'An anonymous supporter')
            amount = kofi_data.get('amount', 'a donation')
            message = kofi_data.get('message', '')

            formatted_amount = f"${float(amount):.2f}"
            thank_you_message = f"Wow! A new donation! Thank you so much, {name}, for the {formatted_amount}!"
            speaking_queue.put({'text': thank_you_message, 'state': 'happy'})

            if message:
                time.sleep(2)
                message_to_read = f"{name} says: {message}"
                speaking_queue.put({'text': message_to_read, 'state': 'talking'})

        self.send_response(200)
        self.end_headers()

    # We can still silence the logs to keep the console clean
    def log_message(self, format, *args):
        pass


# Your start_web_server function remains the same
def start_web_server(port=8000):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, KofiWebhookHandler)
    print(f"--- Starting local web server on http://localhost:{port} ---")
    httpd.serve_forever()


def start_streamlabs_listener():
    if not STREAMLABS_TOKEN:
        print("--- Streamlabs token not found, listener disabled. ---")
        return
    print("--- Starting Streamlabs listener... ---")

    @sio.event
    def connect():
        print("--- Streamlabs connection established. ---")

    @sio.event
    def disconnect():
        print("--- Streamlabs disconnected. ---")

    @sio.event
    def event(data):
        # The raw data print statement has been removed.

        event_type = data.get('type')
        if not event_type:
            return # Ignore events without a type

        # NEW: A list of event types to silently ignore.
        # You can add more event types to this list in the future if needed.
        ignored_events = ['rollEndCredits']
        if event_type in ignored_events:
            return # Exit quietly if the event type is in our ignore list.

        # Only try to parse message data for events we know should have it.
        if event_type in ['follow', 'subscription', 'bits']:
            messages = data.get('message')

            # If 'message' key is missing or the list is empty, stop.
            if not messages:
                print(f"--- Streamlabs: Received '{event_type}' event with no message data. Skipping. ---")
                return

            message = messages[0]
            name = message.get('name')

            # If the user's name is missing, stop.
            if not name:
                print(f"--- Streamlabs: Received '{event_type}' event with no name. Skipping. ---")
                return

            # Now that we've safely gotten the data, handle the event.
            if event_type == 'follow':
                print(f"--- STREAMLABS EVENT: Follow from {name} ---")
                save_stream_label(LATEST_FOLLOWER_FILE, f"Latest Follower: {name}    ")
                thank_you_message = f"Hey, a new follower! Thank you so much for the follow, {name}!"
                speaking_queue.put({'text': thank_you_message, 'state': 'happy'})

            elif event_type == 'subscription':
                print(f"--- STREAMLABS EVENT: Subscription from {name} ---")
                save_stream_label(LATEST_SUBSCRIBER_FILE, f"Latest Subscriber: {name}    ")

            elif event_type == 'bits':
                amount = message.get('amount', '0')
                print(f"--- STREAMLABS EVENT: Cheer from {name} for {amount} bits ---")
                save_stream_label(LATEST_CHEER_FILE, f"Latest Cheer: {name} - {amount}    ")
        else:
            # This will still let you know about any other genuinely new event types.
            print(f"--- Streamlabs: Received unhandled event type '{event_type}'. ---")


    sio.connect(f'https://sockets.streamlabs.com?token={STREAMLABS_TOKEN}', transports=['websocket'])
    sio.wait()


async def create_eventsub_subscription(websocket, session_id):
    """Sends requests to Twitch to subscribe to the events we care about."""
    headers = {'Authorization': f'Bearer {EVENTSUB_OAUTH_TOKEN}', 'Client-ID': TWITCH_CLIENT_ID,
               'Content-Type': 'application/json'}
    # ADDED 'channel.subscription.message' and 'channel.subscription.gift'
    topics = [
        {"type": "channel.channel_points_custom_reward_redemption.add", "version": "1",
         "condition": {"broadcaster_user_id": TWITCH_USER_ID}},
        {"type": "channel.follow", "version": "2",
         "condition": {"broadcaster_user_id": TWITCH_USER_ID, "moderator_user_id": TWITCH_USER_ID}},
        {"type": "channel.subscribe", "version": "1", "condition": {"broadcaster_user_id": TWITCH_USER_ID}},
        {"type": "channel.subscription.message", "version": "1", "condition": {"broadcaster_user_id": TWITCH_USER_ID}}, # <-- FOR RESUBS
        {"type": "channel.subscription.gift", "version": "1", "condition": {"broadcaster_user_id": TWITCH_USER_ID}},      # <-- FOR GIFTED SUBS
        {"type": "channel.cheer", "version": "1", "condition": {"broadcaster_user_id": TWITCH_USER_ID}},
        {"type": "channel.ad_break.begin", "version": "1", "condition": {"broadcaster_user_id": TWITCH_USER_ID}}
    ]
    for topic in topics:
        body = {"type": topic["type"], "version": topic["version"], "condition": topic["condition"],
                "transport": {"method": "websocket", "session_id": session_id}}
        try:
            response = await asyncio.get_running_loop().run_in_executor(None, lambda: http_requests.post(
                'https://api.twitch.tv/helix/eventsub/subscriptions', headers=headers, json=body))
            response.raise_for_status()
            print(f"--- EventSub: Subscribed to '{topic['type']}' successfully! ---")
        except Exception as e:
            print(f"!!! EventSub: Failed to subscribe to '{topic['type']}': {e} !!!")


async def run_eventsub_listener_async():
    """Connects to Twitch's EventSub WebSocket to listen for real-time events."""
    uri = "wss://eventsub.wss.twitch.tv/ws"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                welcome_message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=30))
                if welcome_message['metadata']['message_type'] == 'session_welcome':
                    session_id = welcome_message['payload']['session']['id']
                    await create_eventsub_subscription(websocket, session_id)
                    while True:
                        message = json.loads(await websocket.recv())
                        if message['metadata']['message_type'] == 'notification':
                            payload = message['payload']
                            event = payload['event']
                            sub_type = payload['subscription']['type']
                            # --- THIS IS THE FIX ---
                            # Safely get the user_name from the event, with a default value.
                            user_name = event.get('user_name', 'Someone')
                            if sub_type == 'channel.follow':
                                save_stream_label(LATEST_FOLLOWER_FILE, f"Latest Follower: {event['user_name']}    ")
                            elif sub_type == 'channel.subscribe':
                                # This event handles NEW subs and Prime subs. Gift subs are handled separately.
                                if not event.get('is_gift', False):
                                    tier = event.get('tier', '1000')
                                    thank_you_message = ""
                                    if tier == 'prime':
                                        thank_you_message = f"Wow, a Prime Gaming sub! Thank you so much, {user_name}, for linking up your systems to support the channel!"
                                    else:
                                        thank_you_message = f"A new subscriber! Welcome to the Saturn Crew, {user_name}! It's so cool to have you here!"

                                    save_stream_label(LATEST_SUBSCRIBER_FILE, f"Latest Subscriber: {user_name}    ")
                                    speaking_queue.put({'text': thank_you_message, 'state': 'happy'})

                            elif sub_type == 'channel.subscription.message':
                                # This event handles RESUBS
                                months = event.get('cumulative_total', 1)
                                user_message = event.get('message', {}).get('text', '')

                                thank_you_message = f"A resub! {user_name} has been part of the crew for {months} months! Thank you for your amazing support!"

                                save_stream_label(LATEST_SUBSCRIBER_FILE,
                                                  f"Latest Resub: {user_name} ({months} mo)    ")
                                speaking_queue.put({'text': thank_you_message, 'state': 'happy'})

                            elif sub_type == 'channel.subscription.gift':
                                # This event handles GIFTED subs
                                total_gifts = event.get('total', 1)
                                gifter_name = "An anonymous gifter" if event.get('is_anonymous', True) else user_name

                                if total_gifts > 1:
                                    thank_you_message = f"INCOMING SUB BOMBS! {gifter_name} just gifted {total_gifts} subs to the community! That's incredible, thank you so much!"
                                else:
                                    thank_you_message = f"A gift sub! {gifter_name} just gifted a subscription to the community! Thank you for sharing the love!"

                                speaking_queue.put({'text': thank_you_message, 'state': 'excited'})
                            elif sub_type == 'channel.cheer':
                                user = event.get('user_name', 'Anonymous')
                                if event.get('is_anonymous', False):
                                    user = "An anonymous cheerer"
                                bits = event.get('bits', 0)

                                save_stream_label(LATEST_CHEER_FILE, f"Latest Cheer: {user} - {bits}    ")

                                thank_you_message = ""
                                state = 'happy'

                                if bits >= 10000:
                                    state = 'excited'
                                    thank_you_message = f"CRITICAL ERROR! High-generosity overflow! Thank you SO, SO MUCH {user}, for the {bits} bits!"
                                elif bits >= 5000:
                                    state = 'excited'
                                    thank_you_message = f"OH MY GOSH! Thank you for the massive {bits} bits, {user}! That is incredible!"
                                elif bits > 0:
                                    thank_you_message = f"Wow! Thank you for the {bits} bits, {user}!"

                                if thank_you_message:
                                    speaking_queue.put({'text': thank_you_message, 'state': state})

                            elif sub_type == 'channel.ad_break.begin':
                                duration = event['duration_seconds']
                                message = f"Heads up, Saturn Crew! A {duration} second ad break is starting now. Thank you so much for your support, it keeps the lights on! We'll be right back. (≧∇≦)"
                                send_twitch_message(message)
                                speaking_queue.put({'text': message, 'state': 'talking'})

                            elif sub_type == 'channel.channel_points_custom_reward_redemption.add':
                                # All reward logic is now correctly nested inside this block
                                reward_title = event['reward']['title']
                                user_name = event['user_name']
                                user_input = event.get('user_input', '')

                                if reward_title == "Ask A.M.I. a Question":
                                    if user_input:
                                        request_queue.put({
                                            'username': user_name,
                                            'question': user_input,
                                            'send_func': send_twitch_message,
                                            'source': 'twitch_eventsub'
                                        })
                                        send_twitch_message(
                                            f"@{user_name}, A.M.I. has received your question and will answer shortly! (≧∇≦)")
                                    else:
                                        send_twitch_message(f"@{user_name}, you forgot to enter a question!")

                                elif reward_title == "A.M.I. says a quote":
                                    response_text = random.choice(QUOTES)
                                    speaking_queue.put({'text': response_text, 'state': 'talking'})
                                    send_twitch_message(f"@{user_name} redeemed a quote! A.M.I. says: \"{response_text}\"")

                                elif reward_title == "A.M.I. shares a fact":
                                    response_text = random.choice(RETRO_FACTS)
                                    speaking_queue.put({'text': response_text, 'state': 'talking'})
                                    send_twitch_message(f"@{user_name} redeemed a fact! A.M.I. Factoid: {response_text}")

                                elif reward_title == "Hydration Check!":
                                    response_text = f"Hey Willy, {user_name} says it's time to drink some water!"
                                    speaking_queue.put({'text': response_text, 'state': 'happy'})
                                    send_twitch_message(f"💧 Stay hydrated! {user_name} redeemed a hydration check! 💧")

                                elif reward_title == "Impose a Challenge!":
                                    if user_input:
                                        response_text = f"{user_name} has redeemed a new challenge! Willy, you must now {user_input}"
                                        speaking_queue.put({'text': response_text, 'state': 'talking'})
                                        send_twitch_message(
                                            f"A new challenge has been issued by {user_name}! Willy must now: {user_input}")
                                    else:
                                        send_twitch_message(f"@{user_name}, you forgot to enter a challenge!")

                                elif reward_title == '"SEGA!" Chant':
                                    response_text = f"{user_name} wants to hear the music! Willy, clear your throat, it is time to sing the iconic SEGA chorus!"
                                    speaking_queue.put({'text': response_text, 'state': 'happy'})
                                    send_twitch_message(f"Get ready, everyone! {user_name} has redeemed the SEGA Chant!")

                                elif reward_title == "Timeout a Friend (10s)":
                                    target_user = user_input.strip().lstrip('@').lower()
                                    immune_users = [CHANNEL.lower(), NICK.lower(), 'streamlabs', 'streamelements', 'nightbot']

                                    if not target_user:
                                        send_twitch_message(f"@{user_name}, you forgot to enter a username to time out!")
                                    elif target_user in immune_users:
                                        send_twitch_message(
                                            f"@{user_name}, you can't time out a protected user! (Nice try, though! 😉)")
                                    else:
                                        send_twitch_message(
                                            f"/timeout {target_user} 10 Timed out by {user_name} via Channel Points!")
                                        send_twitch_message(
                                            f"Watch out! {user_name} just used their power to put {target_user} in the penalty box for 10 seconds!")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"!!! EventSub: Connection closed with code {e.code}. Reconnecting in 30 seconds... !!!")
            await asyncio.sleep(30)
        except Exception as e:
            print(f"!!! A critical error occurred in EventSub listener: {e}. Reconnecting in 30 seconds... !!!")
            await asyncio.sleep(30)


def run_eventsub_listener():
    asyncio.run(run_eventsub_listener_async())


def run_eventsub_listener():
    """A simple wrapper to run the asynchronous EventSub listener."""
    asyncio.run(run_eventsub_listener_async())


# --- MAIN TWITCH BOT CONNECTION ---
def run_twitch_bot():
    """The core function that connects to Twitch chat (IRC) and listens for messages."""
    global twitch_socket, emote_combo_tracker, emote_combo_cooldowns
    load_strikes()
    load_toxicity_strikes()
    load_infraction_strikes()
    set_ami_state('neutral')
    twitch_socket = socket.socket()
    twitch_socket.connect((HOST, PORT))
    twitch_socket.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
    twitch_socket.send(f"PASS {TOKEN}\n".encode('utf-8'))
    twitch_socket.send(f"NICK {NICK}\n".encode('utf-8'))
    twitch_socket.send(f"JOIN #{CHANNEL}\n".encode('utf-8'))
    print(f"{NICK} connected to #{CHANNEL}.")
    send_twitch_message(f"{NICK} is now online and operational. ✨")

    buffer = ""
    try:
        while True:
            buffer += twitch_socket.recv(4096).decode('utf-8')
            messages = buffer.split('\r\n')
            buffer = messages.pop()

            for line in messages:
                if line.startswith("PING"):
                    twitch_socket.send(b"PONG :tmi.twitch.tv\r\n")
                    print("PONG sent.")
                    continue

                if "PRIVMSG" in line:
                    try:
                        tags_raw = line.split(' ')[0]
                        tags = {tag.split('=')[0]: tag.split('=')[1] for tag in tags_raw[1:].split(';') if '=' in tag}
                        badges_str = tags.get('badges', '')
                        parts = line.split(":", 2)
                        user_info = parts[1].split("!", 1)
                        username = user_info[0]
                        msg_content = parts[2].strip()

                        if moderate_message(username, msg_content, badges_str):
                            continue

                        if msg_content.startswith('!'):
                            handle_command(send_twitch_message, username, tags.get('badges', {}), msg_content, 'twitch')

                        # Event Triggers
                        if event_mode == "HALLOWEEN" and "spooky" in msg_content.lower():
                            trigger_lightning_flash(username)
                        if "teto" in msg_content.lower():
                            trigger_teto_plush(username)
                        if "pearto" in msg_content.lower():
                            trigger_pearto(username)

                    except IndexError:
                        continue
                elif "USERNOTICE" in line:
                    try:
                        tags_raw = line.split(' ')[0]
                        tags = {tag.split('=')[0]: tag.split('=')[1] for tag in tags_raw[1:].split(';') if '=' in tag}
                        handle_user_notice(tags)
                    except Exception as e:
                        print(f"Could not handle USERNOTICE: {line} | Error: {e}")
    except Exception as e:
        print(f"A critical error occurred in Twitch bot: {e}")
    finally:
        print("Closing Twitch connection.")
        if twitch_socket: twitch_socket.close()


# --- NEW: Function to load initial stream labels from files ---
def load_stream_labels():
    """Reads the last known stream labels from files on startup."""
    if not os.path.exists(LATEST_FOLLOWER_FILE):
        save_stream_label(LATEST_FOLLOWER_FILE, "Latest Follower: None    ")
    if not os.path.exists(LATEST_SUBSCRIBER_FILE):
        save_stream_label(LATEST_SUBSCRIBER_FILE, "Latest Subscriber: None    ")
    if not os.path.exists(LATEST_CHEER_FILE):
        save_stream_label(LATEST_CHEER_FILE, "Latest Cheer: None    ")


# =================================================================================================
# --- MAIN EXECUTION BLOCK ---
# =================================================================================================
if __name__ == "__main__":
    validate_and_refresh_tokens()
    load_trivia_questions()
    load_trivia_scores()
    load_death_counter()
    load_strikes()
    load_toxicity_strikes()
    load_infraction_strikes()
    load_stream_labels()

    web_server_thread = threading.Thread(target=start_web_server, daemon=True)
    twitch_thread = threading.Thread(target=run_twitch_bot, daemon=True)
    streamlabs_thread = threading.Thread(target=start_streamlabs_listener, daemon=True)
    askami_worker_thread = threading.Thread(target=askami_worker, daemon=True)
    trivia_worker_thread = threading.Thread(target=trivia_worker, daemon=True)
    speaking_worker_thread = threading.Thread(target=speaking_worker, daemon=True)
    eventsub_thread = threading.Thread(target=run_eventsub_listener, daemon=True)

    web_server_thread.start()
    twitch_thread.start()
    streamlabs_thread.start()
    askami_worker_thread.start()
    trivia_worker_thread.start()
    speaking_worker_thread.start()
    eventsub_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown signal received. Closing connections.")
        if sio.connected:
            sio.disconnect()