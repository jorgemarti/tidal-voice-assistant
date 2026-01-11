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

    return logger

# Retry Configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
RETRY_BACKOFF_MULTIPLIER = 2

# Tidal Configuration
TIDAL_CONFIG = {
    'quality': 'LOSSLESS',  # Options: 'LOSSLESS', 'HIGH', 'LOW'
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
# Add your custom wake phrases here (Vosk uses unaccented text)
# The system also uses a flexible regex pattern for variations
# Include common Vosk misrecognitions
WAKE_WORDS = [
    'okay musica',    # No accent - Vosk uses unaccented
    'okey musica',
    'okey musical',
    'okay musical',
    'okay muy sica',  # Common misrecognition
    'okey muy sica',
    'okay muisica',
    'okey muisica',
]

# Custom wake word regex pattern (optional)
# Set to None to use default pattern: ok/okay/okey + musica/música/musical
# Example: r'\b(hey|hola)\s*(tidal)\b' for "Hey Tidal" or "Hola Tidal"
WAKE_WORD_PATTERN = None

# Speech Recognition Configuration
VOSK_MODEL_PATH = "vosk-model-small-es-0.42"  # Small Spanish model for wake word detection
SPEECH_TIMEOUT = 8  # Seconds to listen for command after wake word

# Command Recognition Configuration (Hybrid Architecture)
# Wake word detection: Vosk (local, fast, offline)
# Command recognition: Google Speech API (cloud, accurate, free)
COMMAND_RECOGNITION = 'google'  # Options: 'google', 'vosk' (fallback)
COMMAND_LANGUAGE = 'es-ES'  # Spanish (Spain) for Google Speech API

# Audio Configuration
SAMPLE_RATE = 44100
CHANNELS = 1
CHUNK_SIZE = 8000
AUDIO_INPUT_DEVICE_INDEX = 1  # USB PnP Sound Device (hw:2,0)

# Voice Activity Detection (VAD) - reduces CPU usage by only processing speech
VAD_ENABLED = True  # Enable VAD to reduce CPU from ~20% to ~5%
VAD_AGGRESSIVENESS = 2  # 0-3, higher = more aggressive filtering (fewer false positives)

# TTS Configuration
TTS_ENGINE = 'google'  # Options: 'google' (Google Translate TTS), 'local' (pyttsx3, offline)
TTS_LOCAL_RATE = 175  # Speech rate for local TTS (words per minute)
TTS_LOCAL_VOICE = None  # None = system default, or specify voice name
TTS_SHORT_ANNOUNCEMENTS = False  # If True, use brief announcements (just track name)

# Search Cache Configuration
SEARCH_CACHE_ENABLED = True  # Cache Tidal search results
SEARCH_CACHE_TTL = 300  # Cache time-to-live in seconds (5 minutes)
SEARCH_CACHE_MAX_SIZE = 50  # Maximum number of cached searches

# Note: Tidal authentication now uses OAuth device flow
# No credentials needed in .env file
