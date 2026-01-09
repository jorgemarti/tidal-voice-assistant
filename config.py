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

# Wake Word Configuration
WAKE_WORDS = [
    'okay musica',    # No accent - Vosk uses unaccented
    'okey musica',
    'okey musical',
]

# Speech Recognition Configuration
VOSK_MODEL_PATH = "vosk-model-es-0.42"  # Large Spanish model (1.4GB, better accuracy)
SPEECH_TIMEOUT = 8  # Seconds to listen for command after wake word

# Audio Configuration
SAMPLE_RATE = 44100
CHANNELS = 1
CHUNK_SIZE = 8000
AUDIO_INPUT_DEVICE_INDEX = 0  # Set to None to use default, or specify device ID from list_audio_devices.py

# Note: Tidal authentication now uses OAuth device flow
# No credentials needed in .env file
