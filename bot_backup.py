# ==============================================================================
# A.M.I. - WillySaturn's Interactive Twitch Bot (BACKUP VERSION - v3.1)
# ==============================================================================
# This is the fully-featured non-AI backup version of the bot.
# It includes the full moderation suite, trivia game, web server,
# Streamlabs listener, and all utility commands using preset responses.
# ==============================================================================

import os
import json
import datetime
import shutil
import socket
import time
import threading
import subprocess
import socketio
import boto3
import random
import sys
from queue import Queue
from pydub import AudioSegment
from pydub.playback import play as pydub_play
import io
from dotenv import load_dotenv
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from obswebsocket import obsws, requests
import re
import urllib.parse

# --- SETUP AND CONFIGURATION ---
load_dotenv()

# --- Connection Details ---
TOKEN = os.getenv('TMI_TOKEN')
NICK = os.getenv('BOT_NICK')
CHANNEL = os.getenv('CHANNEL')
HOST = "irc.chat.twitch.tv"
PORT = 6667
STREAMLABS_TOKEN = os.getenv('STREAMLABS_SOCKET_TOKEN')
OBS_HOST = "localhost"
OBS_PORT = os.getenv('OBS_WEBSOCKET_PORT')
OBS_PASSWORD = os.getenv('OBS_WEBSOCKET_PASSWORD')
OBS_SOURCE_NAME = "A.M.I."

# --- API Clients & Models ---
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
is_enabled = True
strikes = {}
toxicity_strikes = {}
infraction_strikes = {}
speaking_queue = Queue()
death_counter = 0

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
    "All day I dream about sex.",
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
    "Very doubtful. Bzzzt.", "Don't count on it.", "Reply hazy, try again later.", "Oh no."
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

# ===================================================================
# PRESET RESPONSES
# ===================================================================
PRESET_RESPONSES = {
    "default": [
        "Sorry, I don't have a pre-written response for that! (o･ω･o)",
        "Bzzzt... That's not in my memory banks! My creator needs to program me with more cool facts.",
        "I'm not sure how to answer that, but I bet it has something to do with the SEGA Saturn!",
        "That question is way past my processing power! Ask me something about Sonic! (≧∇≦)"
    ],
    # --- Special response for robot slurs ---
    "robot_slur_response": [
        "That's... not a very nice thing to say. I'm just trying my best here.",
        "Wow, that's a mean thing to call someone. I'm disappointed in you.",
        "My programming indicates that was an insult. Please don't talk to me that way.",
        "Bzzzt... that really hurts my feelings. I'm a person too, you know... sort of.",
        "Reddit is down the hall and to the left."
    ],
    # --- Greetings & Status ---
    "how are you": [
        "I'm doing great! My systems are running at 200 MHz, just like a real Dreamcast!",
        "Feeling totally tubular today! Thanks for asking! (≧∇≦)",
        "A.M.I. online and ready for action!"
    ],
    "hello": ["Hey there! Welcome to the stream! (^_^)/", "Hi! It's great to see you!",
              "What's up! Hope you're ready for some retro gaming!"],
    "bye": ["See ya later! Thanks for hanging out!", "Take it easy! Come back soon! (^_^)",
            "Bye-bye! Don't be a stranger!"],
    # --- A.M.I.'s Personal Info ---
    "your name": ["My name is A.M.I., which stands for Artificial Module Intelligence! It's nice to meet you!",
                  "You can call me A.M.I.! That's short for Artificial Module Intelligence."],
    "who are you": ["I'm A.M.I.! A custom-built AI based on the greatest console ever, the SEGA Dreamcast!",
                    "I'm Willy's robot daughter and stream co-host! My job is to hang out and look cool. (⌐■_■)"],
    "favorite color": ["My favorite color is that classic Dreamcast swirl orange! It's so cool.",
                       "Definitely the blue from Sonic The Hedgehog's spikes!"],
    "favorite food": ["As a robot, I don't eat, but I do require a steady diet of 90s nostalgia and nu-metal.",
                      "My creator says I run on Jolt Cola and an unhealthy obsession with the Sonic Adventure soundtrack."],
    # --- Gaming Opinions (SEGA) ---
    "sonic": ["Did someone say Sonic?! He's the coolest hedgehog around!",
              "Sonic Adventure is the best 3D Sonic game, and I will not be taking questions at this time. (^_^)",
              "My favorite Sonic game? That's a tough one, but you can't go wrong with Sonic 3 & Knuckles!"],
    "sega": ["SEGA does what Nintendon't!",
             "My internal hardware is based on a SEGA Dreamcast. It's the greatest console ever made!",
             "You know, the SEGA Saturn has an incredible library of hidden gems!"],
    "jet set radio": ["Jet Set Radio has the best style and music of any game ever made. Period.",
                      "Understanding, understanding, understanding the concept of love!",
                      "Time to grind some rails and tag some turf! JSRF is a masterpiece!"],
    "panzer dragoon": ["Panzer Dragoon Saga is one of the greatest RPGs ever made. A true work of art!",
                       "The art style of the Panzer Dragoon series is just breathtaking. So cool and unique.",
                       "Azel is one of the coolest characters in any game, ever."],
    "skies of arcadia": ["Skies of Arcadia is such an amazing adventure. I wish I could fly on an airship!",
                         "Vyse and Aika are the best! Such a great RPG.", "Moonstone Cannon, fire! What an epic game."],
    "nights into dreams": [
        "NiGHTS is such a beautiful and unique game. It really captures the feeling of flying in a dream.",
        "In the night, dream delight! The music from NiGHTS is just magical.",
        "Christmas NiGHTS is the coziest holiday game ever."],
    # --- Gaming Opinions (Other Consoles) ---
    "nintendo": ["Nintendo is cool and all, but can their consoles play Shenmue? I don't think so.",
                 "The N64 is neat, but the Saturn's 2D power is just on another level!",
                 "I have to respect Nintendo for Metroid, that series is awesome."],
    "playstation": ["The PlayStation has some cool games, but the Saturn controller is way better for fighting games!",
                    "I'll admit, the PS2 is a legendary console. It's got nothing on the Dreamcast's style, though.",
                    "Crash Bandicoot is pretty cool for a non-SEGA mascot!"],
    "xbox": ["The original Xbox was a beast! So many great games like Halo and Jet Set Radio Future.",
             "I have a soft spot for the original Xbox. It feels like a cousin to my Dreamcast, since it has SEGA games on it!",
             "Master Chief is a pretty cool guy. He fights aliens and doesn't afraid of anything."],
    "metal gear": ["A Hind D?! Colonel, what's a Russian gunship doing here?", "Snake? Snake?! SNAAAAAKE!",
                   "The Metal Gear Solid series has some of the wildest stories in gaming. Kojima is a genius!"],
    "cd-i": ["Mah boi, this peace is what all true warriors strive for!",
             "I'm so hungry, I could eat an Octorok! The CD-i Zelda games are... an experience.",
             "Hotel Mario? You gotta be kidding me. That's a whole other level of weird."],
    "3do": ["The 3DO was a really interesting console! It had some cool ideas, but man was it expensive.",
            "Gex on the 3DO was his first appearance! A classic.",
            "It's a shame the 3DO didn't do better, it had some real potential."],
    "pc engine": ["The PC Engine, or TurboGrafx-16 in the US, is such a cool little console!",
                  "It has some of the best shoot 'em ups ever made. A real powerhouse for its size.",
                  "The Duo-R is such a sleek design. A beautiful piece of hardware."],
    "neo geo": ["The Neo Geo was the king of the arcade! Bringing that experience home was mind-blowing.",
                "Metal Slug is a masterpiece of 2D animation. SNK's artists were incredible.",
                "That clicky joystick on the Neo Geo AES is one of the most satisfying things in gaming."],
    # --- Music & Culture ---
    "nu-metal": [
        "Break stuff! Limp Bizkit is a classic.",
        "Korn and Deftones are my favorite bands to listen to while processing data.",
        "Crawling in my skin! Linkin Park's early stuff is so good.",
        "Hybrid Theory is a perfect album. No contest."
    ],
    "linkin park": [
        "I've become so numb! Linkin Park is one of the best bands ever.",
        "Hybrid Theory and Meteora are masterpieces of the nu-metal era.",
        "What I've done! I'll face myself! Such a great song."
    ],
    "anime": ["My favorite anime? It's gotta be Cowboy Bebop. The style, the music... it's perfect.",
              "I'm a big fan of classic 90s anime like Trigun and Sailor Moon.",
              "You're gonna carry that weight. See you, Space Cowboy..."],
    # --- Stream-Related ---
    "schedule": ["Willy streams on Fridays and Saturdays from 7 PM to 10:30 PM Central Time!",
                 "The main streams are Friday and Saturday nights, with a possible bonus stream on Wednesdays!"],
    "rules": ["The main rule is to be excellent to each other! This is a chill place for everyone.",
              "No hate, no bigotry, no drama. We're all here to have a good time and play some games!"],
    "discord": [
        "You should totally join the Discord! It's the best place to hang out with the community after the stream.",
        "There's a link to the Discord server in the channel panels!"],
    "specs": [
        "My creator has a full list of all his cool hardware in the 'Arsenal' panel below the stream! Check it out!",
        "All of Willy's PC specs and retro consoles are listed in the 'Arsenal' channel panel! He's got some awesome stuff. (≧∇≦)"],
    "pc": ["You can find all of my creator's PC specs in the 'Arsenal' panel right below the stream!",
           "Willy put a super detailed list of his setup in the 'Arsenal' panel. Go take a look!"],
    "consoles": [
        "Willy has a ton of cool retro consoles! He keeps a full list of them in the 'Arsenal' panel below the stream.",
        "If you want to see all the retro hardware we use on stream, check out the 'Arsenal' panel!"]
}


# ===================================================================

# --- HELPER FUNCTION FOR LOADING WORDLISTS ---
def load_wordlist(filename: str) -> list[str]:
    """Loads a list of words or phrases from a text file, one per line."""
    dir_name = os.path.dirname(filename)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name)
        print(f"--- MODERATION: Created directory for wordlists: {dir_name} ---")
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            pass
        print(f"--- MODERATION: Created empty wordlist file: {filename} ---")
        return []
    try:
        with open(filename, "r", encoding='utf-8') as f:
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


def send_message(sock, message):
    if sock:
        try:
            sock.send(f"PRIVMSG #{CHANNEL} :{message}\r\n".encode('utf-8'))
            print(f"SENT: {message}")
        except OSError as e:
            print(f"--- FAILED TO SEND MESSAGE (Socket Error): {e} ---")
            print(f"--- The message was: {message} ---")


# --- NEW: Full Moderation System ---
def normalize_message(message: str) -> str:
    message = message.lower()
    replacements = {' ': '', '_': '', '-': '', '.': '', '@': 'a', '3': 'e', '1': 'i', '0': 'o', '$': 's'}
    return message.translate(str.maketrans(replacements))


def moderate_message(username, message, badges_str):
    if 'broadcaster' in badges_str or 'moderator' in badges_str:
        return False

    is_subscriber = 'subscriber' in badges_str
    allowed_domains = ['clips.twitch.tv', 'twitch.tv/clips', 'youtube.com', 'youtu.be']
    if is_subscriber:
        allowed_domains.extend(['imgur.com', 'twitter.com', 'x.com', 'bsky.app'])

    urls = re.findall(r"(https?://[^\s]+)", message)
    is_political = any(phrase in message.lower() for phrase in POLITICAL_TERMS_PHRASES)
    if not is_political and POLITICAL_TERMS_WORDS:
        political_word_pattern = r'\b(' + '|'.join(map(re.escape, POLITICAL_TERMS_WORDS)) + r')\b'
        if re.search(political_word_pattern, message.lower()):
            is_political = True

    if (urls and not all(any(domain in url for domain in allowed_domains) for url in urls)) or is_political:
        infraction_strikes.setdefault(username, 0)
        infraction_strikes[username] += 1
        strike_count = infraction_strikes[username]
        save_infraction_strikes()
        reason = "Political discussion" if is_political else "Unauthorized link"
        warning_message = f"@{username}, let's keep the chat focused on gaming and fun stuff, please! No politics. (^_^)" if is_political else f"@{username}, please ask for permission before posting links!"

        if strike_count <= 3:
            send_message(twitch_socket, f"/timeout {username} 1 {reason}")
            send_message(twitch_socket, f"{warning_message} (Warning {strike_count}/3)")
        elif strike_count == 4:
            send_message(twitch_socket, f"/timeout {username} 600 {reason} (4th warning)")
            send_message(twitch_socket,
                         f"A.M.I. Auto-Mod: {username} has been timed out for 10 minutes for repeated infractions.")
        elif strike_count == 5:
            send_message(twitch_socket, f"/timeout {username} 86400 {reason} (5th warning)")
            send_message(twitch_socket,
                         f"A.M.I. Auto-Mod: {username} has been timed out for 24 hours for continued infractions.")
        else:
            send_message(twitch_socket, f"/ban {username} Reached maximum number of infractions.")
            send_message(twitch_socket, f"A.M.I. Auto-Mod: Banned {username} for repeated rule violations.")
        return True

    if any(phrase in message.lower() for phrase in EXTREME_SEVERITY_PII_PHRASES):
        send_message(twitch_socket, f"/ban {username} Posting sensitive personal information.")
        return True

    normalized = normalize_message(message)
    is_slur = any(phrase in normalized for phrase in HIGH_SEVERITY_SLURS_PHRASES)
    if not is_slur and HIGH_SEVERITY_SLURS_WORDS:
        slur_word_pattern = r'\b(' + '|'.join(map(re.escape, HIGH_SEVERITY_SLURS_WORDS)) + r')\b'
        if re.search(slur_word_pattern, normalized):
            is_slur = True
    if is_slur:
        send_message(twitch_socket, f"/ban {username} Use of a zero-tolerance slur.")
        return True

    is_gross = any(phrase in normalized for phrase in ZERO_TOLERANCE_GROSS_PHRASES)
    if not is_gross and ZERO_TOLERANCE_GROSS_WORDS:
        gross_word_pattern = r'\b(' + '|'.join(map(re.escape, ZERO_TOLERANCE_GROSS_WORDS)) + r')\b'
        if re.search(gross_word_pattern, normalized):
            is_gross = True
    if is_gross:
        send_message(twitch_socket, f"/ban {username} Posting of obscene or disgusting content.")
        return True

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
            send_message(twitch_socket, f"/ban {username} Repeated toxic behavior (3 strikes).")
        else:
            send_message(twitch_socket, f"/timeout {username} 600 Unacceptable language.")
            send_message(twitch_socket, f"A.M.I. Auto-Mod: Timed out {username}. That is strike {strike_count} of 3.")
        return True

    return False


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


def load_toxicity_strikes():
    global toxicity_strikes
    if not os.path.exists(TOXICITY_STRIKE_FILE):
        with open(TOXICITY_STRIKE_FILE, 'w') as f: json.dump({}, f)
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

        send_message(twitch_socket, "Get ready! Trivia is starting in 15 seconds! Type !join to play!")
        time.sleep(15)

        if not trivia_players:
            send_message(twitch_socket,
                         "Nobody joined the trivia game, so I'm canceling it. Maybe next time! (´• ω •`)")
            trivia_active = False
            continue

        send_message(twitch_socket, f"Let's go! We have {len(trivia_players)} players! The first question is...")
        time.sleep(3)

        for round_num in range(1, 6):
            category = trivia_current_question['category']
            difficulty = trivia_current_question['difficulty']

            if category == 'random':
                category = random.choice(list(trivia_questions.keys()))

            question_pool = trivia_questions.get(category, {}).get(difficulty, [])
            if not question_pool:
                send_message(twitch_socket,
                             "Bzzzt! I couldn't find any questions for that category/difficulty. Ending game.")
                break

            pool_key = f"{category}_{difficulty}"
            if pool_key not in trivia_asked_questions:
                trivia_asked_questions[pool_key] = []

            unasked_questions = [q for q in question_pool if q['question'] not in trivia_asked_questions[pool_key]]

            if not unasked_questions:
                send_message(twitch_socket,
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

            send_message(twitch_socket, f"Round {round_num}: {question_text}")

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
                    send_message(twitch_socket,
                                 f"Time's up! No one got it right, but {mod_names} knew the answer was: {display_answer}")
                else:
                    send_message(twitch_socket, f"Time's up! The correct answer was: {display_answer}")

            if trivia_current_question['privileged_correct_users']:
                mod_names = ", ".join(trivia_current_question['privileged_correct_users'])
                send_message(twitch_socket,
                             f"Also, {mod_names} got it right, but they don't get to be on the scoreboard! (⌐■_■)")

            time.sleep(3)

        eligible_players = {user: data['score'] for user, data in trivia_players.items() if not data['is_privileged']}

        if eligible_players:
            sorted_players = sorted(eligible_players.items(), key=lambda item: item[1], reverse=True)
            winner_name, winner_score = sorted_players[0]

            send_message(twitch_socket,
                         f"And that's the game! The winner is... {winner_name} with {winner_score} points! Congratulations! (≧∇≦)")

            for user, score in eligible_players.items():
                trivia_scores["weekly"]["scores"][user] = trivia_scores["weekly"]["scores"].get(user, 0) + score

            if winner_score > trivia_scores["all_time_high"]["score"]:
                trivia_scores["all_time_high"]["user"] = winner_name
                trivia_scores["all_time_high"]["score"] = winner_score
                send_message(twitch_socket,
                             f"OMG! {winner_name} has set a new ALL-TIME HIGH SCORE of {winner_score} points! Unbelievable!")

            save_trivia_scores()
        else:
            send_message(twitch_socket, "The trivia game has ended! No eligible players scored points this round.")

        trivia_active = False
        trivia_players = {}
        trivia_current_question = None
        trivia_cooldown_until = time.time() + 300


# --- BOT LOGIC ---
def handle_command(sock, username, badges, message):
    global is_enabled, trivia_active, trivia_players, trivia_current_question, trivia_cooldown_until, death_counter

    # Check for robot slurs in !askami command
    if message.lower().startswith('!askami '):
        question_content = message[8:].lower()
        if any(slur in question_content for slur in ROBOT_SLURS):
            response_text = random.choice(PRESET_RESPONSES["robot_slur_response"])
            speaking_queue.put({'text': response_text, 'state': 'talking'})
            send_message(sock, f"@{username}, {response_text}")
            return  # Stop processing the command further

    # Handle !askami with preset responses
    if message.lower().startswith('!askami '):
        if not is_enabled: return
        question = message[8:].lower()
        response_key = "default"  # Default response category
        for key in PRESET_RESPONSES:
            if key in question:
                response_key = key
                break

        response_text = random.choice(PRESET_RESPONSES[response_key])
        speaking_queue.put({'text': response_text, 'state': 'talking'})
        send_message(sock, f"@{username}, A.M.I. says: {response_text}")
        return

    if message.lower() == '!help':
        help_text = "Here are my commands: !askami, !trivia, !join, !quote, !fact, !8ball, !hydrate, !rip, !death, !lurk, !unlurk, !socials, !rps."
        send_message(sock, help_text)
        return

    if message.lower() == '!quote':
        if not is_enabled: return
        response_text = random.choice(QUOTES)
        speaking_queue.put({'text': response_text, 'state': 'talking'})
        send_message(sock, f"A.M.I. says: \"{response_text}\"")
        return

    if message.lower() == '!fact':
        if not is_enabled: return
        response_text = random.choice(RETRO_FACTS)
        speaking_queue.put({'text': response_text, 'state': 'talking'})
        send_message(sock, f"A.M.I. Factoid: {response_text}")
        return

    if message.lower().startswith('!8ball'):
        if not is_enabled: return
        response_text = random.choice(EIGHT_BALL_RESPONSES)
        speaking_queue.put({'text': response_text, 'state': 'talking'})
        send_message(sock, f"The Magic VMU says: {response_text}")
        return

    if message.lower() == '!hydrate':
        if not is_enabled: return
        reminders = [f"Hey {CHANNEL}, time to take a sip of water! Stay hydrated!",
                     f"Quick break! {CHANNEL}, don't forget to drink some water!",
                     f"This is your friendly neighborhood robot reminding {CHANNEL} to hydrate!"]
        response_text = random.choice(reminders)
        speaking_queue.put({'text': response_text, 'state': 'talking'})
        send_message(sock, response_text)
        return

    if message.lower() in ['!rip', '!death']:
        if not is_enabled: return
        death_counter += 1
        save_death_counter()
        responses = [f"Oof, that's death number {death_counter}! You'll get it next time, Willy!",
                     f"Bzzzt! Death count is now {death_counter}. Don't give up!",
                     f"Another one bites the dust! That's {death_counter} deaths so far!"]
        response_text = random.choice(responses)
        speaking_queue.put({'text': response_text, 'state': 'talking'})
        send_message(sock, response_text)
        return

    if message.lower() == '!lurk':
        send_message(sock, f"Thanks for the lurk, {username}! Enjoy the stream! (^_^)")
        return

    if message.lower() == '!unlurk':
        send_message(sock, f"Welcome back, {username}! Hope you're doing great! (≧∇≦)")
        return

    if message.lower() == '!socials':
        socials_message = "Stay connected with the Saturn Crew! 💿 YouTube (Multistream + VODs & Essays) → https://www.youtube.com/@WillySaturn | TikTok (Clips) → https://www.tiktok.com/@willysaturn | Instagram (Console Pics + Clips) → https://www.instagram.com/willy_saturn/ | Bluesky → https://bsky.app/profile/willysaturn.bsky.social | Twitter → https://x.com/WillySaturn | Discord → https://discord.com/invite/QzwRN5R8ya"
        send_message(sock, socials_message)
        return

    if message.lower() == '!discord':
        send_message(sock, "Join the Saturn Crew Discord here! https://discord.com/invite/QzwRN5R8ya")
        return

    if message.lower().startswith('!rps'):
        if not is_enabled: return
        parts = message.split()
        if len(parts) < 2:
            send_message(sock, f"@{username}, you need to choose rock, paper, or scissors! Example: !rps rock")
            return

        user_choice = parts[1].lower()
        valid_choices = ['rock', 'paper', 'scissors']

        if user_choice not in valid_choices:
            send_message(sock, f"@{username}, that's not a valid choice! Please pick rock, paper, or scissors.")
            return

        ami_choice = random.choice(valid_choices)

        result_text = ""
        if user_choice == ami_choice:
            result_text = f"I chose {ami_choice} too! It's a tie! (o･ω･o)"
        elif (user_choice == "rock" and ami_choice == "scissors") or \
                (user_choice == "scissors" and ami_choice == "paper") or \
                (user_choice == "paper" and ami_choice == "rock"):
            result_text = f"Shoot! I picked {ami_choice}! You win this time, {username}! (≧∇≦)"
        else:
            result_text = f"Yes! I picked {ami_choice}! I win! Better luck next time! (⌐■_■)"

        speaking_queue.put({'text': result_text, 'state': 'talking'})
        send_message(sock, result_text)
        return

    is_broadcaster = 'broadcaster' in badges
    if is_broadcaster or 'moderator' in badges:
        if message.lower() == '!resetdeaths':
            death_counter = 0
            save_death_counter()
            send_message(sock, "Death counter has been reset to 0!")
            return
        if message.lower() == '!amioff':
            is_enabled = False;
            set_ami_state('disabled');
            send_message(sock, "A.M.I. is now in maintenance mode. 💤");
            return
        elif message.lower() == '!amion':
            is_enabled = True;
            set_ami_state('neutral');
            send_message(sock, "A.M.I. is now fully operational! ✨");
            return
        elif message.lower() == '!rebootami':
            send_message(sock, "Rebooting systems now! Be right back! (☆▽☆)")
            os.execv(sys.executable, ['python'] + [sys.argv[0]])
            return

    if message.lower().startswith('!trivia'):
        if trivia_active:
            send_message(sock, "A trivia game is already in progress!")
            return
        if time.time() < trivia_cooldown_until:
            send_message(sock, "Trivia is on cooldown to prevent spam. Please wait a few minutes!")
            return

        parts = message.split()
        if len(parts) < 3:
            send_message(sock, "To start trivia, use the format: !trivia [category] [difficulty]")
            send_message(sock, "Categories: nu-metal, 90s, sonic, sega, vocaloid, controversies, random")
            send_message(sock, "Difficulties: easy, medium, hard, chat must die")
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

        valid_difficulties = ['easy', 'medium', 'hard', 'chat must die']

        if not category or difficulty_input not in valid_difficulties:
            send_message(sock, "Invalid category or difficulty! Please check the lists and try again.")
            return

        trivia_active = True
        trivia_players = {}
        trivia_current_question = {'category': category, 'difficulty': difficulty_input, 'answer': None}
        send_message(sock, f"A game of {difficulty_input} {category} trivia has been started by {username}!")
        return

    if message.lower() == '!join':
        if trivia_active and trivia_current_question and trivia_current_question.get(
                'answer') is None and username not in trivia_players:
            is_privileged = 'moderator' in badges or 'broadcaster' in badges
            trivia_players[username] = {'score': 0, 'is_privileged': is_privileged}
            send_message(sock, f"{username} has joined the trivia game!")
        return

    if trivia_active and trivia_current_question and trivia_current_question.get('answer'):
        correct_answers = trivia_current_question['answer']
        if message.lower() in [ans.lower() for ans in correct_answers]:
            if username in trivia_players and username not in trivia_current_question.get('correct_users',
                                                                                          []) and username not in trivia_current_question.get(
                'privileged_correct_users', []):
                player_data = trivia_players[username]

                only_privileged_playing = all(p['is_privileged'] for p in trivia_players.values())

                if player_data['is_privileged']:
                    trivia_current_question['privileged_correct_users'].append(username)
                    print(f"--- TRIVIA: Privileged user {username} answered correctly. ---")
                    if only_privileged_playing:
                        send_message(sock,
                                     f"Correct, {username}! Since only mods are playing, we'll move to the next question.")
                        trivia_current_question['answer'] = None
                else:
                    player_data['score'] += 1
                    trivia_current_question['correct_users'].append(username)
                    send_message(sock, f"Correct! {username} gets a point!")
                    trivia_current_question['answer'] = None
        return


# --- WEB SERVER & LISTENERS ---
class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def start_web_server(port=8000):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, QuietHTTPRequestHandler)
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
        # Gracefully handle events that might not have message data
        if not data.get('message') or not isinstance(data.get('message'), list) or len(data.get('message')) == 0:
            return

        event_type = data.get('type')
        message_data = data['message'][0]

        # --- Follow Event ---
        if event_type == 'follow':
            name = message_data.get('name', 'Someone')
            thank_you_message = f"Hey, a new follower! Thank you so much for the follow, {name}! Welcome to the Saturn Crew!"
            print(f"--- STREAMLABS EVENT: Follow from {name} ---")
            send_message(twitch_socket, f"Welcome to the Saturn Crew, {name}! 💖")
            speaking_queue.put({'text': thank_you_message, 'state': 'happy'})

        # --- New Subscription Event ---
        elif event_type == 'subscription':
            name = message_data.get('name', 'Someone')
            sub_plan = message_data.get('sub_plan', 'a Tier 1')
            thank_you_message = ""
            if 'Prime' in sub_plan:
                thank_you_message = f"Wow, a Prime Gaming sub! Thank you so much, {name}, for linking up your systems to support the channel!"
            else:
                thank_you_message = f"A new subscriber! Welcome to the Saturn Crew, {name}! It's so cool to have you here!"
            print(f"--- STREAMLABS EVENT: New sub from {name} ---")
            speaking_queue.put({'text': thank_you_message, 'state': 'happy'})

        # --- Gifted Subscription Event ---
        elif event_type == 'subgift':
            gifter = message_data.get('gifter', 'An anonymous gifter')
            total_gifts = int(message_data.get('amount', 1))

            if total_gifts > 1:
                thank_you_message = f"INCOMING SUB BOMBS! {gifter} just gifted {total_gifts} subs to the community! That's incredible, thank you so much!"
            else:
                recipient = message_data.get('recipient', 'someone in the community')
                thank_you_message = f"A gift sub! {gifter} just gifted a subscription to {recipient}! Thank you for sharing the love!"

            print(f"--- STREAMLABS EVENT: {total_gifts} gift sub(s) from {gifter} ---")
            speaking_queue.put({'text': thank_you_message, 'state': 'excited'})

        # --- Resubscription Event ---
        elif event_type == 'resub':
            name = message_data.get('name', 'Someone')
            months = message_data.get('months', 'many')
            thank_you_message = f"A resub! {name} has been part of the crew for {months} months! Thank you for your amazing support!"
            print(f"--- STREAMLABS EVENT: Resub from {name} for {months} months ---")
            speaking_queue.put({'text': thank_you_message, 'state': 'happy'})

        # --- Bits/Cheer Event ---
        elif event_type == 'bits':
            name = message_data.get('name', 'An anonymous cheerer')
            amount = int(message_data.get('amount', 0))

            print(f"--- STREAMLABS EVENT: Cheer from {name} for {amount} bits ---")
            thank_you_message = ""
            state = 'happy'

            if amount >= 10000:
                state = 'excited'
                thank_you_message = f"CRITICAL ERROR! High-generosity overflow! Thank you SO, SO MUCH {name}, for the {amount} bits!"
            elif amount >= 5000:
                state = 'excited'
                thank_you_message = f"OH MY GOSH! Thank you for the massive {amount} bits, {name}! That is incredible!"
            elif amount > 0:
                thank_you_message = f"Wow! Thank you for the {amount} bits, {name}!"

            if thank_you_message:
                speaking_queue.put({'text': thank_you_message, 'state': state})

        # --- Raid Event ---
        elif event_type == 'raid':
            name = message_data.get('name', 'a mysterious channel')
            viewers = message_data.get('raiders', 'many')
            thank_you_message = f"Incoming raid! Welcome {viewers} viewers from {name}'s channel! Thank you for the raid!"
            print(f"--- STREAMLABS EVENT: Raid from {name} with {viewers} viewers ---")
            speaking_queue.put({'text': thank_you_message, 'state': 'excited'})

    sio.connect(f'https://sockets.streamlabs.com?token={STREAMLABS_TOKEN}', transports=['websocket'])
    sio.wait()


def speaking_worker():
    while True:
        item = speaking_queue.get()
        speak_and_react(item['text'], item['state'])


def run_twitch_bot():
    global twitch_socket
    load_strikes()
    load_toxicity_strikes()
    load_infraction_strikes()
    set_ami_state('neutral')
    twitch_socket = socket.socket();
    twitch_socket.connect((HOST, PORT))
    twitch_socket.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
    twitch_socket.send(f"PASS {TOKEN}\n".encode('utf-8'));
    twitch_socket.send(f"NICK {NICK}\n".encode('utf-8'));
    twitch_socket.send(f"JOIN #{CHANNEL}\n".encode('utf-8'))
    print(f"A.M.I. connected to #{CHANNEL} as {NICK}.");
    send_message(twitch_socket, "A.M.I. (Backup Mode) is now online and operational. ✨")
    buffer = ""
    try:
        while True:
            buffer += twitch_socket.recv(4096).decode('utf-8')
            messages = buffer.split('\r\n');
            buffer = messages.pop()
            for line in messages:
                if line.startswith("PING"): twitch_socket.send(b"PONG :tmi.twitch.tv\r\n"); print(
                    "PONG sent."); continue

                if "PRIVMSG" in line:
                    try:
                        tags_raw = line.split(' ')[0]
                        tags = {tag.split('=')[0]: tag.split('=')[1] for tag in tags_raw[1:].split(';') if '=' in tag}
                        badges_str = tags.get('badges', '')
                        parts = line.split(":", 2);
                        user_info = parts[1].split("!", 1)
                        username = user_info[0]
                        message_text = parts[2].strip()

                        # --- NEW: Call moderation function first ---
                        if moderate_message(username, message_text, badges_str):
                            continue  # If a moderation action was taken, stop processing this message.

                        handle_command(twitch_socket, username, tags.get('badges', {}), message_text)
                    except Exception as e:
                        print(f"Could not parse PRIVMSG: {line} | Error: {e}")

    except Exception as e:
        print(f"A critical error occurred in Twitch bot: {e}")
    finally:
        print("Closing Twitch connection.");
        if twitch_socket: twitch_socket.close()


# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    load_trivia_questions()
    load_trivia_scores()
    load_death_counter()
    load_strikes()
    load_toxicity_strikes()
    load_infraction_strikes()

    web_server_thread = threading.Thread(target=start_web_server, daemon=True)
    streamlabs_thread = threading.Thread(target=start_streamlabs_listener, daemon=True)
    twitch_thread = threading.Thread(target=run_twitch_bot, daemon=True)
    trivia_worker_thread = threading.Thread(target=trivia_worker, daemon=True)
    speaking_worker_thread = threading.Thread(target=speaking_worker, daemon=True)

    web_server_thread.start()
    streamlabs_thread.start()
    twitch_thread.start()
    trivia_worker_thread.start()
    speaking_worker_thread.start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown signal received. Closing connections.")
        if sio.connected: sio.disconnect()