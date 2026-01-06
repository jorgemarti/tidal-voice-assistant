"""
Configuration file for Tidal Voice Assistant
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Tidal Configuration
TIDAL_CONFIG = {
    'quality': 'LOSSLESS',  # Options: 'LOSSLESS', 'HIGH', 'LOW'
    'session_file': 'tidal_session.json'
}

# Chromecast Configuration
# Replace with your Nest Mini's exact name from Google Home app
CHROMECAST_NAME = "Altavoz Google"  # Your Nest Mini name

# Wake Word Configuration
WAKE_WORDS = ['hey tidal', 'oye tidal']  # Phrases to trigger voice assistant

# Speech Recognition Configuration
VOSK_MODEL_PATH = "vosk-model-es"  # Spanish model directory
SPEECH_TIMEOUT = 5  # Seconds to listen for command after wake word

# Audio Configuration
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 8000

# Tidal Credentials (from environment)
TIDAL_USERNAME = os.getenv('TIDAL_USERNAME')
TIDAL_PASSWORD = os.getenv('TIDAL_PASSWORD')

# Validate required environment variables
if not TIDAL_USERNAME or not TIDAL_PASSWORD:
    print("⚠️  Warning: Tidal credentials not set in .env file")
