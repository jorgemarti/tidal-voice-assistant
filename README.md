# Tidal Voice Assistant for Raspberry Pi

## 🎯 Project Goal

This project creates a voice-controlled Tidal music player using a Raspberry Pi 5 that casts music to a Google Nest Mini. It allows you to use voice commands in Spanish to play music from Tidal, while keeping the Nest Mini's native "Ok Google" functionality for other tasks like weather, timers, and general queries.

**Why this exists**: Google Nest Mini doesn't support Tidal integration reliably, so this solution uses a Raspberry Pi as a bridge to enable voice-controlled Tidal playback.

## 🏗️ Architecture

![Tidal Voice Assistant Architecture](architecture.svg)

**Flow**:
1. Say wake phrase: "Okay música" (or "Okey música")
2. Speak music command in Spanish: "Reproduce Rosalía" (can be in same breath or after beep)
3. Pi transcribes speech to text (Spanish model)
4. Parses command to extract song/artist using phonetic matching
5. Searches Tidal API
6. Announces what will be played, then streams audio to Nest Mini via Chromecast
7. For non-music commands, continue using "Ok Google" directly on Nest Mini

**Note**: Wake word detection uses Vosk with a single full-model recognizer (fully offline). This allows saying wake word + command together naturally.

## 📋 Hardware Requirements

- **Raspberry Pi 5** (4GB+ recommended)
- **MicroSD Card** (32GB+, Class 10)
- **Microphone** (USB Microphone ($15-50))
- **Google Nest Mini** (2nd generation or later)
- Both devices on the same WiFi network

## 🔧 Software Requirements

- Raspberry Pi OS (64-bit recommended)
- Python 3.9+
- Active Tidal subscription

## 📦 Installation

### Step 1: System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv portaudio19-dev git

# Clone this repository
git clone <your-repo-url>
cd tidal-voice-assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### Step 2: Download Spanish Speech Recognition Model

```bash
# Download Vosk Spanish model
wget https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
unzip vosk-model-small-es-0.42.zip
rm vosk-model-small-es-0.42.zip
```

### Step 3: Configure Environment Variables (Optional)

```bash
# Copy example environment file
cp .env.example .env

# Edit to set log level if needed
nano .env
```

You can set the log level:
```bash
LOG_LEVEL=INFO  # Default - INFO, DEBUG, WARNING, ERROR, CRITICAL
```

**Note**: Tidal credentials are no longer needed in `.env` - authentication uses OAuth.

### Step 4: Authenticate with Tidal

```bash
python tidal_auth.py
```

This will:
1. Display a URL to visit in your browser
2. Ask you to authorize the application
3. Save the session for future use

Follow the link, log in to Tidal, and authorize the app.

### Step 5: Test Wake Word Detection

```bash
# Basic test
python test_wake_word.py

# Debug mode - see all transcriptions
python test_wake_word.py --debug

# Test microphone levels
python test_wake_word.py --mic
```

Say "Okay música" to test detection.

### Step 6: Find Your Nest Mini Name

```bash
python test_chromecast.py --discover
```

This will list all Chromecast devices on your network. Note the exact name of your Nest Mini.

### Step 7: Verify Configuration

Check that `config.py` has your correct Nest Mini name:

```python
CHROMECAST_NAME = "Altavoz Google"  # Should match name from discovery
```

## 🧪 Testing Chromecast Connection

Before running the full voice assistant, test that your Pi can cast to the Nest Mini:

### Quick Pychromecast Test

```bash
# Activate virtual environment
source venv/bin/activate

# Run the test script
python test_chromecast.py --test
```

This will:
1. Discover your Nest Mini
2. Generate a test MP3 file with Spanish text-to-speech
3. Cast it to your Nest Mini

### Manual Testing with Custom MP3

If you have your own MP3 file:

```bash
# Place your MP3 in the project directory
cp /path/to/your/music.mp3 ./test_audio.mp3

# Cast it to Nest Mini
python test_chromecast.py --file test_audio.mp3
```

### Testing with Tidal Stream

Test a Tidal track directly:

```bash
python test_tidal.py "Bohemian Rhapsody Queen"
```

### Expected Output

```
Discovering Chromecasts...
Found: Living Room speaker (192.168.1.100)
Found: Bedroom display (192.168.1.101)

Connecting to 'Living Room speaker'...
Connected successfully!

Playing test audio...
Audio should now be playing on your Nest Mini
```

**Troubleshooting**:
- If no devices found: Check both devices are on same WiFi network
- If connection fails: Restart your Nest Mini
- If audio doesn't play: Check Nest Mini volume isn't muted

## 🎤 Microphone Setup

### Test Your Microphone

```bash
# List audio devices
arecord -l

# Record a 5-second test (press Ctrl+C to stop earlier)
arecord -f cd -d 5 test.wav

# Play it back
aplay test.wav
```

### If microphone not working:

```bash
# Set default audio device
nano ~/.asoundrc
```

Add (replace X with your card number from `arecord -l`):
```
pcm.!default {
    type hw
    card X
}

ctl.!default {
    type hw
    card X
}
```

## 🚀 Running the Application

### Interactive Mode (Recommended for testing)

```bash
source venv/bin/activate
python main.py
```

You should see:
```
Initializing Tidal Voice Assistant...
Loading Spanish speech recognition model...
Ready! Say 'Hey Tidal' or 'Oye Tidal' followed by your music command
(Use 'Ok Google' for other commands on Nest Mini)
```

### Example Commands (in Spanish):

**Music playback:**
- **"Okay música, reproduce Rosalía"** → Play song
- **"Okay música, pon música de Bad Bunny"** → Play artist's top tracks
- **"Okay música, reproduce el álbum El Madrileño"** → Play album
- **"Okay música, pon canciones de Metallica"** → Play artist
- **"Okay música, reproduce la playlist rock clásico"** → Play playlist

**Playback controls:**
- **"Okay música, para"** or **"stop"** → Stop playback
- **"Okay música, pausa"** → Pause playback
- **"Okay música, continúa"** or **"sigue"** → Resume playback
- **"Okay música, siguiente"** or **"salta"** → Skip to next track

**Tip**: Spanish artist/song names work best. English names may be misrecognized.

### Non-Music Commands (use Nest Mini directly):

- **"Ok Google, ¿qué tiempo hace?"** → Handled by Nest Mini
- **"Ok Google, pon un temporizador de 5 minutos"** → Handled by Nest Mini
- **"Ok Google, cuéntame un chiste"** → Handled by Nest Mini

## 🔄 Running as a Service (Auto-start on Boot)

```bash
# Copy service file
sudo cp tidal-assistant.service /etc/systemd/system/

# Edit paths if needed
sudo nano /etc/systemd/system/tidal-assistant.service

# Enable and start
sudo systemctl enable tidal-assistant
sudo systemctl start tidal-assistant

# Check status
sudo systemctl status tidal-assistant

# View logs
journalctl -u tidal-assistant -f
```

### Token Renewal

Tidal tokens auto-refresh, but the refresh token expires (~30 days). When this happens:

1. **Voice notification**: The Nest Mini will announce in Spanish: *"Atención. La sesión de Tidal ha caducado. Por favor, ejecuta la autenticación manualmente."*
2. **Manual re-auth required**:
   ```bash
   cd ~/tidal-voice-assistant
   source venv/bin/activate
   python tidal_auth.py
   sudo systemctl restart tidal-assistant
   ```

## 📝 Project Structure

```
tidal-voice-assistant/
├── README.md                    # This file
├── CLAUDE.md                    # Context for Claude Code
├── architecture.svg             # Architecture diagram
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── config.py                    # Application configuration
├── main.py                      # Main application entry point
├── audio_processor.py          # Centralized audio processing (wake word + commands)
├── command_parser.py           # Parse Spanish music commands
├── phonetic_matcher.py         # Phonetic matching for fuzzy search
├── tidal_player.py             # Tidal API and Chromecast integration
├── tidal_auth.py               # Tidal authentication
├── list_audio_devices.py       # List available audio input devices
├── test_chromecast.py          # Chromecast testing utilities
├── test_tidal.py               # Tidal integration testing
├── test_wake_word.py           # Wake word detection testing
├── tidal-assistant.service     # Systemd service file
└── vosk-model-small-es-0.42/   # Spanish speech recognition model (downloaded)
```

## 🐛 Troubleshooting

### Wake Word Not Detected
- Test wake word detection: `python test_wake_word.py --debug`
- Check microphone levels: `python test_wake_word.py --mic`
- List audio devices: `python list_audio_devices.py`
- Verify microphone input: `arecord -l`
- Increase microphone volume: `alsamixer`
- Speak clearly: "Okay música"
- Pause briefly after the wake word if saying command separately

### Speech Recognition Not Working
- Verify Spanish model is downloaded to `vosk-model-small-es-0.42/`
- Test with: `python main.py` and check partial transcriptions in logs
- Test wake word detection: `python test_wake_word.py --debug`

### Chromecast Not Found
- Ensure Pi and Nest Mini on same WiFi network
- Check firewall: `sudo ufw status`
- Restart Nest Mini
- Run discovery: `python test_chromecast.py --discover`

### Tidal Authentication Fails
- Delete `tidal_session.json` and re-run: `python tidal_auth.py`
- Make sure to follow the OAuth URL in your browser
- Verify Tidal subscription is active
- Check internet connection

### Audio Quality Issues
- Increase Tidal quality in `config.py`: `'quality': 'LOSSLESS'`
- Check network bandwidth
- Reduce WiFi interference

### Python Dependencies Issues
```bash
# Reinstall in clean environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 📊 Logging

Set the log level in your `.env` file:

```bash
LOG_LEVEL=INFO      # Default - normal operation
LOG_LEVEL=DEBUG     # Verbose output for troubleshooting
LOG_LEVEL=WARNING   # Only warnings and errors
```

**Where to see logs:**
- **Manual run**: Logs appear in the terminal
- **As a service**: Use `journalctl -u tidal-assistant -f`

## 🔐 Security Notes

- Never commit `.env` file to version control
- Keep `tidal_session.json` private
- All processing is done locally (fully offline wake word detection)

## 🚧 Known Limitations

- Wake word detection uses ~15-25% CPU (continuous Vosk transcription)
- Detection latency: 200-500ms (vs <50ms with cloud-based solutions)
- Requires good audio environment (low background noise)
- Spanish speech recognition works best with clear pronunciation (Spain Spanish)
- Network latency affects response time
- Tidal API rate limits may apply
- Tidal refresh tokens expire (~30 days) - voice notification will alert you

## 🛣️ Future Enhancements

- [x] Fully offline wake word detection (no external APIs)
- [x] Autoplay/continuous playback (queues similar tracks)
- [x] Full album and artist playback (queues all tracks)
- [x] Playlist support
- [x] Skip track functionality
- [ ] Volume control via voice
- [ ] Multi-language support (Catalan, etc.)
- [ ] Web interface for configuration
- [ ] Better error handling and user feedback
- [ ] Integration with Home Assistant

## 🌐 External API Dependencies

This project contacts the following external services:

| Service | Purpose | URL(s) | Library |
|---------|---------|--------|---------|
| **Google Speech API** | Command recognition (after wake word) | `http://www.google.com/speech-api/v2/recognize` | SpeechRecognition |
| **Google Translate TTS** | Voice announcements on Nest Mini | `https://translate.google.com/translate_tts` | Direct URL |
| **Google Actions Sounds** | Activation beep sound | `https://actions.google.com/sounds/v1/alarms/beep_short.ogg` | Direct URL |
| **Tidal API** | Music search, streaming URLs, track radio | `https://api.tidal.com/*` | tidalapi |
| **Tidal Auth** | OAuth authentication | `https://auth.tidal.com/*`, `https://login.tidal.com/*` | tidalapi |

**Local/Offline components:**
- **Vosk** - Wake word detection runs entirely offline using downloaded Spanish model
- **Chromecast** - Communication with Nest Mini happens on local network (mDNS discovery + local streaming)

## 📚 Resources

- [Vosk Speech Recognition](https://alphacephei.com/vosk/)
- [Pychromecast Documentation](https://github.com/home-assistant-libs/pychromecast)
- [Tidal API (tidalapi)](https://github.com/tamland/python-tidal)

## 📄 License

MIT License - feel free to modify and distribute

## 🤝 Contributing

Contributions welcome! Please open an issue or pull request.

## ✨ Credits

Created as a solution for Tidal integration with Google Nest Mini devices.
