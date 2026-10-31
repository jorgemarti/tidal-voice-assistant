"""
Configuration file for Tidal Voice Assistant
"""

import os
import logging
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
# Optional log file (rotating, 5 x 5 MB). The systemd unit sets LOG_FILE=logs/assistant.log so the
# log survives when stdout goes to the journal; without it only stdout is used.
LOG_FILE = os.getenv('LOG_FILE', '')

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _read_version():
    try:
        with open(os.path.join(_BASE_DIR, 'VERSION')) as f:
            return f.read().strip()
    except OSError:
        return '0.0.0'


VERSION = _read_version()
_FILE_HANDLER = None


def _file_handler():
    """One shared rotating file handler for every logger (created on first use)."""
    global _FILE_HANDLER
    if _FILE_HANDLER is None and LOG_FILE:
        from logging.handlers import RotatingFileHandler
        path = LOG_FILE if os.path.isabs(LOG_FILE) else os.path.join(_BASE_DIR, LOG_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _FILE_HANDLER = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
        _FILE_HANDLER.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    return _FILE_HANDLER
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logging(name=None):
    """
    Set up logging for the application.

    Args:
        name: Logger name (default: root logger)

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

        # Console handler with formatting
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        if _file_handler():
            logger.addHandler(_file_handler())

    return logger

# Retry Configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
RETRY_BACKOFF_MULTIPLIER = 2

# Tidal Configuration
TIDAL_CONFIG = {
    'quality': 'HIGH',  # Options: 'LOSSLESS', 'HIGH', 'LOW' (account tier currently returns HIGH)
    'session_file': 'tidal_session.json'
}

# Autoplay Configuration
AUTOPLAY_ENABLED = True  # Enable continuous playback after a song ends
AUTOPLAY_TRACK_COUNT = 10  # Number of similar tracks to queue for autoplay

# Chromecast Configuration
# Replace with your Nest Mini's exact name from Google Home app
CHROMECAST_NAME = "Altavoz Google"  # Your Nest Mini name
CHROMECAST_PRECONNECT = True  # Connect to Chromecast on startup (reduces first-command latency)

# Wake Word Configuration
# Phrases recognised by Vosk in grammar mode (use the model's accented spelling)
WAKE_WORDS = [
    'okey música',
    'okay música',
    'ok música',
]

# Speech Recognition Configuration
VOSK_MODEL_PATH = "vosk-model-small-es-0.42"  # Small Spanish model, used for wake word and local transcript
SPEECH_TIMEOUT = 8  # Max seconds of command audio after the wake word
COMMAND_NO_SPEECH_TIMEOUT = 4.0  # After the prompt cue, give up if nothing is said this long
AUDIO_PRE_WAKE_SECONDS = 1.5  # Audio kept before the wake word detection for the LLM (so it hears the whole sentence)

# Audio Configuration
# The C-Media USB mic only captures at 44.1/48 kHz; plughw lets ALSA resample to 16 kHz for Vosk
AUDIO_DEVICE = "plughw:0,0"
SAMPLE_RATE = 16000

# Command parsing: Gemini Flash (command audio only) with regex fallback
COMMAND_PARSER = 'gemini'  # 'gemini' or 'regex'
GEMINI_MODEL = 'gemini-3.5-flash-lite'
GEMINI_USE_AUDIO = True  # Send the command audio to Gemini; False sends only the Vosk transcript
GEMINI_MAX_PER_HOUR = 40   # Hard caps on Gemini requests: a runaway of false wake triggers cannot drain the prepaid balance
GEMINI_MAX_PER_DAY = 300
# Optional extra artists for Gemini's spelling aid, comma-separated in .env (KNOWN_ARTISTS=...). The library
# already supplies the favourite and most played artists, so this is only for names not in it.
KNOWN_ARTISTS = [a.strip() for a in os.environ.get('KNOWN_ARTISTS', '').split(',') if a.strip()]

# The household library (Tidal favourites and playlists plus the Last.fm top of the last month) is matched
# locally before the Tidal catalogue and sent to Gemini as a closed set of labels (see library.py).
LIBRARY_FILE = 'library.json'
LIBRARY_REFRESH_HOURS = 24
LIBRARY_MATCH_SCORE = 80    # fuzzy score needed to play a library entry without searching the catalogue
LIBRARY_HINT_TRACKS = 120   # labels per kind in the Gemini prompt (about 1,500 tokens in total)
LIBRARY_HINT_ALBUMS = 40
LIBRARY_HINT_ARTISTS = 80
LASTFM_TOP_TRACKS = 50      # most played in the last month, from the scrobbles
LASTFM_TOP_ARTISTS = 30

# TTS Configuration
TTS_ENGINE = 'google'  # Options: 'google' (Google Translate TTS), 'local' (pyttsx3, offline)
TTS_LOCAL_RATE = 175  # Speech rate for local TTS (words per minute)
TTS_LOCAL_VOICE = None  # None = system default, or specify voice name
TTS_SHORT_ANNOUNCEMENTS = False  # If True, use brief announcements (just track name)
TTS_ANNOUNCE_PLAYBACK = False  # Say "Reproduciendo X de Y" before the music starts (adds ~7 s). The music itself is the feedback.
PLAYBACK_CUES = False  # Play the timeout/error cues on the speaker (the wake cue after a pause is always played)
SPEAK_NOT_UNDERSTOOD = False  # Say "No te he entendido" when a command is not a music command. Off: a false wake trigger during a conversation stays silent.

# Last.fm scrobbling of what the speaker plays (needs LASTFM_API_KEY/LASTFM_API_SECRET in .env and `python lastfm_auth.py` once)
LASTFM_SCROBBLE = True
LASTFM_SESSION_FILE = 'lastfm_session.json'

# Search Cache Configuration
SEARCH_CACHE_ENABLED = True  # Cache Tidal search results
SEARCH_CACHE_TTL = 300  # Cache time-to-live in seconds (5 minutes)
SEARCH_CACHE_MAX_SIZE = 50  # Maximum number of cached searches

# Note: Tidal authentication now uses OAuth device flow
# No credentials needed in .env file
