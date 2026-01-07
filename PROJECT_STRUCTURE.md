# Project Structure

```
tidal-voice-assistant/
│
├── README.md                    # Main documentation and setup guide
├── CLAUDE.md                    # Context file for Claude Code development
├── PROJECT_STRUCTURE.md         # This file - detailed project structure
├── architecture.svg             # System architecture diagram
├── LICENSE                      # MIT License
│
├── setup.sh                     # Automated setup script
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore patterns
│
├── config.py                    # Application configuration
├── main.py                      # Main application entry point
│
├── tidal_auth.py               # Tidal OAuth authentication
├── wake_word.py                # Wake word detection (Vosk)
├── speech_recognition.py       # Spanish speech-to-text (Vosk)
├── command_parser.py           # Parse Spanish music commands
├── tidal_player.py             # Tidal API + Chromecast integration
│
├── test_chromecast.py          # Test Chromecast connectivity
├── test_tidal.py               # Test Tidal integration
├── test_wake_word.py           # Test wake word detection
│
├── tidal-assistant.service     # Systemd service for auto-start
│
├── venv/                       # Python virtual environment (created by setup)
├── vosk-model-es/              # Spanish speech model (downloaded)
└── tidal_session.json          # Tidal OAuth session (created on first run)
```

## File Descriptions

### Documentation

**README.md**
- Complete project documentation
- Hardware and software requirements
- Installation instructions
- Testing procedures (including pychromecast testing)
- Usage examples
- Troubleshooting guide
- References architecture.svg for visual overview

**architecture.svg**
- Visual system architecture diagram
- Shows complete data flow from voice input to audio output
- Includes Raspberry Pi components, Tidal API, and Google Nest Mini
- Color-coded components and clear connection arrows

**CLAUDE.md**
- Context file for Claude Code
- Contains conversation history and requirements
- Technical architecture details
- Development priorities and roadmap
- For use when continuing development with Claude

**PROJECT_STRUCTURE.md** (this file)
- Detailed breakdown of project files
- Purpose and description of each component

**LICENSE**
- MIT License for the project

### Setup and Configuration

**setup.sh**
- Automated setup script
- Installs system dependencies
- Creates virtual environment
- Downloads Spanish Vosk model
- Creates .env file from template

**requirements.txt**
- Python package dependencies:
  - vosk: Speech recognition and wake word detection
  - pyaudio: Audio capture
  - tidalapi: Tidal API integration
  - pychromecast: Chromecast protocol
  - python-dotenv: Environment variables
  - gtts: Text-to-speech for testing

**.env.example**
- Template for environment variables
- User copies to `.env` and fills in:
  - TIDAL_USERNAME
  - TIDAL_PASSWORD

**.gitignore**
- Git ignore patterns
- Excludes: venv/, .env, *.pyc, vosk models, etc.

**config.py**
- Central configuration file
- Loads environment variables
- Defines:
  - Tidal settings (quality, session file)
  - Chromecast name
  - Wake word phrases
  - Speech recognition parameters
  - Audio settings

### Core Application

**main.py**
- Main application entry point
- Orchestrates all components
- Main loop:
  1. Wait for wake word
  2. Capture voice command
  3. Parse Spanish command
  4. Search Tidal
  5. Play on Chromecast
- Error handling and logging
- Clean shutdown on Ctrl+C

### Components

**tidal_auth.py**
- Handles Tidal authentication using OAuth device flow
- Functions:
  - `authenticate_tidal()`: OAuth device flow with browser authorization
  - `save_session()`: Persist OAuth tokens
  - `load_tidal_session()`: Load or create session
- Creates `tidal_session.json` file with OAuth tokens
- Can be run standalone to authenticate with Tidal

**wake_word.py**
- Wake word detection using Vosk (fully offline)
- Class: `WakeWordDetector`
- Methods:
  - `__init__()`: Initialize Vosk recognizer
  - `listen()`: Block until wake word detected
  - `get_model()`: Return Vosk model for sharing with other components
  - `cleanup()`: Release resources
- Default wake phrases: "hey tidal", "oye tidal"
- No external API dependencies
- Note: Picovoice was evaluated but not used to reduce dependencies

**speech_recognition.py**
- Offline Spanish speech recognition using Vosk
- Class: `SpeechRecognizer`
- Methods:
  - `__init__(model=None)`: Load Spanish model or use shared model
  - `listen_for_command()`: Capture and transcribe
  - `listen_continuous()`: Continuous mode (optional)
  - `cleanup()`: Release audio resources
- Uses: vosk-model-small-es-0.42
- Supports model sharing with wake_word.py to save ~250MB RAM
- Timeout configurable (default: 5 seconds)

**command_parser.py**
- Parse Spanish voice commands
- Class: `MusicCommandParser`
- Methods:
  - `parse()`: Extract action and query from text
  - `get_search_type()`: Convert to Tidal search type
- Patterns:
  - "reproduce [canción]" → play_song
  - "pon música de [artista]" → play_artist
  - "reproduce el álbum [nombre]" → play_album
- Returns: `{'action': str, 'query': str}`

**tidal_player.py**
- Tidal API integration and Chromecast casting
- Class: `TidalPlayer`
- Methods:
  - `find_chromecast()`: Discover device on network (with 10s timeout)
  - `search_tidal()`: Search by query and type
  - `play_track()`: Play single track
  - `play_artist_top_tracks()`: Play artist's top songs
  - `play_album()`: Play album
  - `search_and_play()`: Combined search and play
  - `stop()`, `pause()`, `play()`: Playback control
  - `cleanup()`: Release Chromecast browser resources
- Integrates: tidalapi + pychromecast

### Testing Utilities

**test_chromecast.py**
- Comprehensive Chromecast testing tool
- Features:
  - Device discovery on network
  - Connection testing
  - Audio playback test
- Modes:
  - `--discover`: List all Chromecast devices
  - `--test`: Full connection and playback test
  - `--file <mp3>`: Test with custom audio file
- Includes HTTP server for serving audio
- Generates Spanish TTS test audio
- **Key for initial setup**: Verifies Pi can cast to Nest Mini

**test_tidal.py**
- Test Tidal integration
- Features:
  - Search testing
  - Playback testing
- Usage:
  - `python test_tidal.py "query" [track|artist|album]`
  - `--search-only`: Just search, don't play
- Validates Tidal authentication and API access

**test_wake_word.py**
- Comprehensive wake word detection testing
- Features:
  - Basic wake word detection test
  - Debug mode: shows all transcriptions
  - Microphone level monitoring
- Usage:
  - `python test_wake_word.py`: Basic test
  - `python test_wake_word.py --debug`: See all transcriptions
  - `python test_wake_word.py --mic`: Test microphone levels
  - `python test_wake_word.py --all`: Run all tests
- Essential for troubleshooting wake word issues

### Service Configuration

**tidal-assistant.service**
- Systemd service file for auto-start
- Runs application as user `pi`
- Auto-restart on failure
- Logs to journal
- Installation:
  ```bash
  sudo cp tidal-assistant.service /etc/systemd/system/
  sudo systemctl enable tidal-assistant
  sudo systemctl start tidal-assistant
  ```

## Generated Files (not in repo)

**venv/**
- Python virtual environment
- Created by `setup.sh` or manually
- Contains all Python packages

**vosk-model-es/**
- Spanish speech recognition model
- ~244MB download
- Downloaded by `setup.sh` or manually

**tidal_session.json**
- OAuth tokens for Tidal API
- Created by `tidal_auth.py`
- Contains: token_type, access_token, refresh_token, expiry_time
- **Important**: Keep private, don't commit

**.env**
- Environment variables (created from .env.example)
- Contains log level configuration (optional)
- **Important**: Keep private if you add sensitive data, don't commit

## Data Flow

```
1. Microphone → wake_word.py → Wake word detected
                      ↓
2. Microphone → speech_recognition.py → Spanish text
                      ↓
3. Spanish text → command_parser.py → {action, query}
                      ↓
4. {action, query} → tidal_player.py → Search Tidal
                      ↓
5. Search results → tidal_player.py → Get stream URL
                      ↓
6. Stream URL → pychromecast → Google Nest Mini
                      ↓
7. Audio playback on Nest Mini
```

## Development Workflow

### Initial Setup
```bash
./setup.sh
source venv/bin/activate
nano .env  # Add credentials
python tidal_auth.py
python test_chromecast.py --discover
```

### Testing
```bash
# Test components individually
python wake_word.py
python speech_recognition.py
python command_parser.py
python test_chromecast.py --test
python test_tidal.py "bohemian rhapsody" track

# Test full application
python main.py
```

### Running
```bash
# Manual run
source venv/bin/activate
python main.py

# As service
sudo systemctl start tidal-assistant
sudo systemctl status tidal-assistant
journalctl -u tidal-assistant -f
```

## Key Design Decisions

1. **Offline Speech Recognition**: Vosk for privacy and no internet dependency
2. **Spanish Model**: Spain variant (es-ES) for accurate recognition
3. **Wake Word**: Vosk-based (fully offline, no external APIs)
   - Picovoice was evaluated but not used to reduce external dependencies
4. **Modular Design**: Each component can be tested independently
5. **Config-Driven**: Easy to customize without code changes
6. **Comprehensive Testing**: Utilities for every component
7. **Service Mode**: Can run as background service

## Dependencies Summary

### System Packages
- python3, python3-pip, python3-venv
- portaudio19-dev (audio I/O library)
- git, unzip, wget (utilities)

### Python Packages
- vosk (speech recognition and wake word detection)
- pyaudio (audio capture)
- tidalapi (Tidal API)
- pychromecast (Chromecast)
- python-dotenv (config)
- gtts (testing only)

### External Assets
- vosk-model-small-es-0.42 (244MB)
- Tidal subscription (required)

## Security Considerations

- **OAuth Tokens**: Never commit tidal_session.json (contains OAuth tokens)
- **Authentication**: OAuth device flow - no passwords stored
- **Privacy**: All wake word detection is fully offline (no cloud)
- **Network**: All devices must be on same WiFi
- **Permissions**: Service runs as user, not root

## Future Enhancements

See CLAUDE.md for detailed roadmap. Key items:
- Playlist support
- Better error handling
- Web interface
- Multi-language (Catalan)
- Home Assistant integration
- Optimize wake word CPU usage
