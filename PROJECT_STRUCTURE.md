# Project Structure

```
tidal-voice-assistant/
│
├── README.md                    # Main documentation and setup guide
├── CLAUDE.md                    # Project context for coding assistants
├── PROJECT_STRUCTURE.md         # This file: detailed project structure
├── improvements.md              # Future improvement ideas
├── architecture.svg             # System architecture diagram
├── LICENSE                      # MIT License
│
├── VERSION                      # Semantic version, read by config.py
├── setup.sh                     # Automated setup script (on the Pi)
├── deploy.sh                    # rsync to the Pi, pip install, service restart
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore patterns
│
├── config.py                    # Application configuration, logging, version
├── main.py                      # Main application entry point
│
├── tidal_auth.py               # Tidal OAuth authentication
├── lastfm_scrobbler.py         # Last.fm scrobbling (optional)
├── library.py                  # Household library (favourites, playlists, Last.fm top): matched first, closed set for Gemini
├── lastfm_auth.py              # One-time Last.fm authorisation
├── audio_processor.py          # ALSA capture (arecord), Vosk wake word, energy-based end of speech
├── llm_parser.py               # Gemini command parser (command audio)
├── command_parser.py           # Regex parser for Spanish music commands (fallback)
├── phonetic_matcher.py         # Phonetic matching (legacy phonetic_search_and_play path)
├── tidal_player.py             # Tidal API + Chromecast integration
├── tts_engine.py               # Text-to-speech (Google or local pyttsx3)
├── utils.py                    # Utility functions and decorators
│
├── test_chromecast.py          # Test Chromecast connectivity
├── test_tidal.py               # Test Tidal integration
├── tests/                      # Unit tests (python -m pytest tests -q)
│   ├── test_command_parser.py
│   ├── test_lastfm_scrobbler.py
│   ├── test_library.py
│   └── test_phonetic_matcher.py
│
├── tidal-assistant.service     # Systemd service for auto-start
│
├── venv/                       # Python virtual environment (created by setup)
├── vosk-model-small-es-0.42/   # Spanish Vosk model (downloaded)
├── logs/                       # Rotating log file when LOG_FILE is set (gitignored)
├── tidal_session.json          # Tidal OAuth session (created by tidal_auth.py)
└── lastfm_session.json         # Last.fm session key (created by lastfm_auth.py)
```

## File Descriptions

### Documentation

**README.md**
- Complete project documentation
- Hardware and software requirements
- Installation instructions, including microphone setup with ALSA
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
- Project context for coding assistants
- Contains requirements and conversation history
- Technical architecture details
- Development priorities and roadmap

**PROJECT_STRUCTURE.md** (this file)
- Detailed breakdown of project files
- Purpose and description of each component

**LICENSE**
- MIT License for the project

### Setup and Configuration

**VERSION**
- Single line with the semantic version (currently `2.0.0`)
- Read by `config.py` as `VERSION`, logged at startup and printed by `python main.py --version`
- Bump it and tag the release (`git tag v2.0.0`)

**deploy.sh**
- Run from the workstation: rsyncs the project to the Pi (`PI_HOST`, default `cockemc@192.168.1.54`, into `~/tidal-voice-assistant`), excluding `venv`, the Vosk model, `.env`, session files, `logs` and `.git`
- Installs `requirements.txt` in the Pi venv, restarts `tidal-assistant` and prints the service status and the last lines of `logs/assistant.log`
- `./deploy.sh --install` also copies the unit to `/etc/systemd/system`, reloads systemd and enables it

**setup.sh**
- Automated setup script, run on the Pi
- Installs system dependencies (alsa-utils, python3-venv, python3-pip, git)
- Creates virtual environment with `--system-site-packages`
- Downloads Spanish Vosk model
- Creates .env file from template
- Prints the amixer commands to raise the mic gain and disable AGC

**requirements.txt**
- Python package dependencies:
  - vosk: wake word detection (grammar mode) and local transcript
  - google-genai: Gemini command parsing from the command audio
  - tidalapi: Tidal API integration
  - pychromecast: Chromecast protocol
  - python-dotenv: Environment variables
  - requests: HTTP utilities
  - fuzzywuzzy, python-Levenshtein: fuzzy candidate selection; g2p-en, nltk: legacy phonetic matcher
  - gtts, pyttsx3: text-to-speech (Google and local)
  - pylast: Last.fm scrobbling (optional)
  - pytest: unit tests

**.env.example**
- Template for environment variables
- User copies to `.env` and fills in:
  - GEMINI_API_KEY (required for the Gemini command parser)
  - LOG_LEVEL (optional)
  - LASTFM_API_KEY, LASTFM_API_SECRET (optional, Last.fm scrobbling)

**.gitignore**
- Git ignore patterns
- Excludes: venv/, .env, *.pyc, vosk models, etc.

**config.py**
- Central configuration file
- Loads environment variables, reads `VERSION`, sets up logging (`setup_logging`: stdout plus a `RotatingFileHandler` of 5 x 5 MB when `LOG_FILE` is set, as the systemd unit does)
- Defines:
  - Tidal settings (quality `HIGH`, session file)
  - Chromecast name (`Altavoz Google`) and pre-connect
  - Wake word phrases (`WAKE_WORDS`) and Vosk model path
  - Command capture timing (`SPEECH_TIMEOUT`, `COMMAND_NO_SPEECH_TIMEOUT`, `AUDIO_PRE_WAKE_SECONDS`)
  - Audio capture (`AUDIO_DEVICE = "plughw:0,0"`, `SAMPLE_RATE = 16000`)
  - Command parser (`COMMAND_PARSER`, `GEMINI_MODEL`, `GEMINI_USE_AUDIO`, `KNOWN_ARTISTS` as a spelling aid for Gemini)
  - TTS and cues (`TTS_ENGINE`, `TTS_ANNOUNCE_PLAYBACK = False`, `PLAYBACK_CUES = False`), autoplay and search cache settings
  - Last.fm (`LASTFM_SCROBBLE`, `LASTFM_SESSION_FILE`)

### Core Application

**main.py**
- Main application entry point; `python main.py --version` prints the version, and startup logs "Tidal Voice Assistant v2.0.0 starting"
- Orchestrates all components
- Pre-connects to the Chromecast, then runs `AudioProcessor` with four callbacks:
  1. `on_wake_word`: pause music if playing (remembering `was_playing`), no cue
  2. `on_prompt`: play the wake cue on the Nest Mini when nothing was heard after the wake word
  3. `on_command`: parse with Gemini. If it answers `unknown`: a control command in Vosk's transcript (para, siguiente, pausa, sigue) is executed; if Gemini heard only the wake phrase or a single word the callback returns `"reprompt"` so the processor cues and listens once more; otherwise "No te he entendido" is spoken and the music resumes if it was playing. The regex parser on the local transcript (two or more words without a verb are searched as a song) is used only when Gemini is unavailable. Music commands go to `tidal_player.smart_search_and_play(query, search_type, artist=..., artist_alternatives=...)`; nothing is announced before the music
  4. `on_timeout`: resume music only if it was playing (timeout cue only with `PLAYBACK_CUES = True`)
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

**audio_processor.py**
- Audio front end, fully offline
- Class: `AudioProcessor`
- Captures audio with `arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -t raw` as a subprocess, read in 100 ms chunks. The C-Media USB mic only captures at 44.1/48 kHz; ALSA's `plughw` resamples to 16 kHz for the Vosk model.
- Two Vosk recognizers fed with the same chunks:
  - wake recognizer in grammar mode (`WAKE_WORDS` plus `[unk]`): about 0.5 s detection, ~3% CPU
  - full recognizer with free vocabulary: the text after the wake phrase is the local transcript, used only as a hint and as the regex fallback input
- End of the command decided by speech energy, not by Vosk's endpointer: the small model is deaf to quiet or distant speech that Gemini hears fine. RMS per 100 ms chunk is compared with a noise floor tracked while idle (`SPEECH_RMS_MIN` 350, `SPEECH_RMS_RATIO` 2.5); `END_SILENCE_SECONDS` (0.9) of silence ends the utterance; energy within `WAKE_TAIL_SECONDS` (0.6) of the wake detection is the tail of "música". `SPEECH_TIMEOUT` (8 s) is the hard cap.
- 20 s ring buffer of audio; the command audio starts `AUDIO_PRE_WAKE_SECONDS` (1.5 s) before the wake detection
- Wake word and command can be said in one breath. If nothing is heard `EARLY_PROMPT_SECONDS` (1.2 s) after the wake word, `on_prompt()` plays a cue and listening continues for `COMMAND_NO_SPEECH_TIMEOUT` (4 s); the transcript is blanked for 1.3 s after the cue so the cue leaking into the mic does not pollute it. A short Vosk residue right after the wake word is kept as "leftover" and sent after `LEFTOVER_WAIT_SECONDS` (2.5 s) if nothing else follows.
- When the handler returns `"reprompt"` (Gemini heard only the wake phrase or a lone verb), the processor cues again and listens once more without dropping the audio queued meanwhile
- Failed listening windows are saved as `/tmp/tidal-commands/timeout-HHMMSS.wav` (with 2 s before the wake) for offline debugging; `/tmp` on the Pi is a 512 MB tmpfs
- Callbacks: `on_wake_word()`, `on_prompt()`, `on_command({'audio', 'transcript', 'sample_rate', 'reprompted'})`, `on_timeout()`
- After each handled command, the audio backlog queued in the `arecord` pipe (TTS, cues) is drained, so the Nest Mini cannot trigger the wake word

**llm_parser.py**
- Command parser backed by Google Gemini
- Class: `LLMCommandParser`
- Methods:
  - `available`: True when `GEMINI_API_KEY` is set and the client initialised
  - `parse(command)`: sends the command audio as WAV, JSON response with minimal thinking, returns `{'action', 'query', 'artist', 'artist_alternatives', 'transcript'}` or None on error
- In audio mode the local Vosk transcript is not sent: it biased the model towards its own mistakes ("strauss" for The Strokes). The artist is kept separate from the query; `artist_alternatives` holds up to 2 guesses when the name was unclear.
- The prompt tells Gemini to keep titles in the language heard (Catalan, English, Portuguese), never to translate, never to add an artist not heard, and to answer `play_artist` for a bare artist name. `KNOWN_ARTISTS` plus the Tidal favourite artists are sent only as a spelling aid.
- Keeps the last 10 command WAVs in `/tmp/tidal-commands/` for debugging
- Model: `GEMINI_MODEL` (`gemini-3.5-flash-lite`); `GEMINI_USE_AUDIO = False` sends only the transcript
- Actions: play_song, play_artist, play_album, play_playlist, stop, pause, resume, skip, unknown
- Measured latency 1.4 to 2 s on the Pi; billing is prepaid (HTTP 402 when depleted)
- Returns None on any error so the regex parser can take over; `unknown` is a valid answer (not a music command), not an error

**command_parser.py**
- Regex parser for Spanish voice commands (fallback when Gemini is unavailable, or the only parser with `COMMAND_PARSER = 'regex'`)
- Class: `MusicCommandParser`
- Methods:
  - `parse()`: Extract action and query from text
  - `get_search_type()`: Convert to Tidal search type
- Patterns:
  - "reproduce [canción]" → play_song
  - "pon música de [artista]" → play_artist
  - "reproduce el álbum [nombre]" → play_album
  - "reproduce la playlist [nombre]" → play_playlist
  - "para", "pausa", "sigue", "siguiente" → stop, pause, resume, skip
- Returns: `{'action': str, 'query': str}`

**phonetic_matcher.py**
- Grapheme-to-phoneme conversion (g2p-en) and fuzzy matching (fuzzywuzzy) of Tidal search results
- Only used by the old `phonetic_search_and_play` path in `tidal_player.py`, which `main.py` no longer calls

**tidal_player.py**
- Tidal API integration and Chromecast casting
- Class: `TidalPlayer`
- Methods:
  - `find_chromecast()`: Discover device on network (with 10s timeout)
  - `search_tidal()`: Search by query and type (cached)
  - `smart_search_and_play(query, search_type, artist=None, artist_alternatives=None)`: Search, pick the best candidate by fuzzy matching on accent-stripped text (fuzzywuzzy `token_set_ratio`, artist name weighted 40% when known; `MATCH_GOOD_SCORE` 75 stops trying alternatives, below `MATCH_MIN_SCORE` 55 it says "No he encontrado...") and play. Tries the artist heard, then its alternatives, then the title alone. Playlists are looked up first in the user's own and favourited playlists (`session.user.playlists()`, `favorites.playlists()`), then the public catalogue. A song query without artist that matches an artist name at 90+ plays the artist instead ("reproduce Pearl Jam").
  - `favourite_artist_names()`: favourited artists and artists of favourited tracks, passed to the LLM parser as a spelling aid
  - `phonetic_search_and_play()`: Legacy path using the phonetic matcher (no longer called from `main.py`)
  - `play_track()`, `play_artist_top_tracks()`, `play_album()`, `play_playlist()`: Play single track, artist, album or playlist; every `play_media` call carries `MusicTrack` metadata (artist, album) built by `_music_metadata()`
  - `stop()`, `pause()`, `play()`, `skip()`, `is_playing()`: Playback control. `pause()` stores the extrapolated position (`status.adjusted_current_time`) so `play()` resumes where the track was; `stop()` does not log an error when nothing was playing
  - `play_audio_cue()`: Short cues ('wake', 'success', 'error', 'timeout') on the Nest Mini
  - `speak()`: TTS message in Spanish ("No te he entendido", "No he encontrado...", token expiry); playback announcements are off (`TTS_ANNOUNCE_PLAYBACK = False`)
  - `_track_info_for(title, artist)`: metadata of a queued track by title, used by the scrobble listener
  - `cleanup()`: Release Chromecast browser resources
- Autoplay: queues similar tracks (track radio), artist top tracks, album or playlist
- Registers `ScrobbleListener` on the media controller in `find_chromecast()` when Last.fm is enabled
- Integrates: tidalapi + pychromecast

**library.py**
- `Library` holds the household's music: Tidal favourite tracks, albums, artists and playlists, the user's own playlists, and the Last.fm top tracks and artists of the last month. `start()` loads `library.json` (or refreshes synchronously the first time) and refreshes every `LIBRARY_REFRESH_HOURS` in a daemon thread.
- `match(query, kind, artist)` is the same fuzzy scoring as the player's catalogue match; `lookup(label)` accepts only labels that exist (the closed set Gemini may copy back as `library_match`); `hint_text()` is the bounded prompt block, most played first; `artist_names()` feeds the spelling aid.
- `TidalPlayer._play_from_library` plays a hit at `LIBRARY_MATCH_SCORE` or above before any catalogue search; Last.fm entries carry no Tidal id and are resolved by one search.

**lastfm_scrobbler.py**
- Optional Last.fm scrobbling via `pylast`; Tidal exposes no listening history
- Class `LastFmScrobbler`: `track_started()` sends "now playing"; `track_ended()` scrobbles once the track played half its length or 4 minutes (`should_scrobble`, tracks over 30 s only), with a guard against scrobbling the same play twice after a pause and resume
- Class `ScrobbleListener`: pychromecast media status listener; resolves the reported title through `_track_info_for`, and trusts the Chromecast's own metadata for tracks queued before a restart. TTS and cues have no artist and are ignored
- Needs `LASTFM_API_KEY` and `LASTFM_API_SECRET` in `.env` and a session key in `lastfm_session.json`; `LASTFM_SCROBBLE = False` turns it off

**lastfm_auth.py**
- One-time desktop authorisation: prints a URL, polls Last.fm until the application is approved (10 min timeout) and saves the session key (never expires) to `lastfm_session.json` with mode 600

**tts_engine.py**
- Text-to-speech backend: Google Translate TTS (default) or local pyttsx3

**utils.py**
- Retry decorator with exponential backoff and other helpers

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

**tests/**
- pytest unit tests: `test_command_parser.py` (regex parser), `test_phonetic_matcher.py`, `test_lastfm_scrobbler.py` (6 tests: scrobble rules, scrobble after enough play, no double scrobble on resume, listener ignores unknown media, position extrapolated between status updates, paused time not counted), `test_library.py` (6 tests: normalisation and labels, fuzzy match by kind, lookup refuses labels outside the library, hint text and artist names, dedupe, save/load)
- Run with `python -m pytest tests -q`. `test_pon_song` in the command parser tests fails (pre-existing, affects only the regex fallback)

### Service Configuration

**tidal-assistant.service**
- Systemd service file for auto-start
- Runs `main.py` from the venv as user `cockemc` in `/home/cockemc/tidal-voice-assistant`, with `.env` as `EnvironmentFile` (`GEMINI_API_KEY`, `LASTFM_*`, `LOG_LEVEL`)
- `Restart=always` with a 10 s delay (arecord dying, Chromecast gone, unhandled errors)
- Logs to the journal (`journalctl -u tidal-assistant -f`) and, through `Environment=LOG_FILE=logs/assistant.log`, to a rotating file (5 x 5 MB) at `~/tidal-voice-assistant/logs/assistant.log`
- Installation: `./deploy.sh --install` from the workstation, or on the Pi:
  ```bash
  sudo cp tidal-assistant.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now tidal-assistant
  ```

## Generated Files (not in repo)

**venv/**
- Python virtual environment
- Created by `setup.sh` or manually with `python3 -m venv --system-site-packages venv`
- Contains all Python packages

**vosk-model-small-es-0.42/**
- Spanish Vosk model, ~58 MB on disk
- Downloaded by `setup.sh` or manually

**tidal_session.json**
- OAuth tokens for Tidal API
- Created by `tidal_auth.py`
- Contains: token_type, access_token, refresh_token, expiry_time
- **Important**: Keep private, don't commit

**lastfm_session.json**
- Last.fm session key, created by `lastfm_auth.py`
- **Important**: Keep private, don't commit

**logs/**
- `assistant.log` and its rotated copies (`assistant.log.1` to `.5`), written when `LOG_FILE` is set (the systemd unit sets it)

**/tmp/tidal-commands/** (on the Pi, tmpfs)
- Last 10 command WAVs sent to Gemini plus `timeout-HHMMSS.wav` for listening windows where nothing was heard; disappears on reboot

**.env**
- Environment variables (created from .env.example)
- Contains `GEMINI_API_KEY`, the optional log level and the optional Last.fm keys
- **Important**: Keep private, don't commit

## Data Flow

```
1. Microphone → arecord (plughw:0,0, 16 kHz) → audio_processor.py → Wake word detected (Vosk grammar mode)
                      ↓
2. Same audio → energy detector ends the command; Vosk full recognizer → local transcript (hint only)
                      ↓
3. Command audio → llm_parser.py (Gemini) → {action, query, artist, artist_alternatives}
   (unknown: control word from the transcript, or re-prompt once, or "No te he entendido";
    only if Gemini is unavailable: transcript → command_parser.py regex)
                      ↓
4. {action, query, artist} → tidal_player.smart_search_and_play() → Search Tidal (fuzzy match, artist weighted; own playlists first)
                      ↓
5. Best candidate → tidal_player.py → stream URL + MusicTrack metadata (no announcement)
                      ↓
6. Stream URL → pychromecast → Google Nest Mini (about 5 s after the end of the command)
                      ↓
7. Audio playback on Nest Mini (autoplay queues more tracks; media status → Last.fm scrobble)
```

## Development Workflow

### Initial Setup
```bash
./setup.sh
source venv/bin/activate
nano .env  # Set GEMINI_API_KEY
amixer -c 0 cset numid=3 16 && amixer -c 0 cset numid=4 off && sudo alsactl store
python tidal_auth.py
python test_chromecast.py --discover
```

### Testing
```bash
# Microphone
arecord -l
arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 5 test.wav && aplay test.wav

# Test components individually
python -m pytest tests -q
python test_chromecast.py --test
python test_tidal.py "bohemian rhapsody" track

# Test full application (LOG_LEVEL=DEBUG in .env shows transcripts and Gemini results)
python main.py
```

### Running
```bash
# Manual run
source venv/bin/activate
python main.py
python main.py --version

# As service
sudo systemctl start tidal-assistant
sudo systemctl status tidal-assistant
journalctl -u tidal-assistant -f
tail -f ~/tidal-voice-assistant/logs/assistant.log
```

### Releasing and deploying
```bash
# Bump VERSION, commit, tag
git tag v2.0.0

# From the workstation: rsync, pip install, restart, status and last log lines
./deploy.sh                # PI_HOST=user@host ./deploy.sh to override the target
./deploy.sh --install      # first time: also install and enable the unit
```

## Key Design Decisions

1. **Offline wake word**: Vosk in grammar mode, no external APIs, about 0.5 s and ~3% CPU
2. **Correct sample rate**: audio captured at 16 kHz through ALSA `plughw` so the Vosk model gets what it expects (the first version fed it 44.1 kHz audio)
3. **Energy-based end of speech**: the small Vosk model misses quiet or distant speech, so the end of the command is decided by RMS over the noise floor and Gemini gets the audio regardless of what Vosk transcribed
4. **Cloud command parsing from audio**: Gemini hears the command itself (the local transcript is not sent, it biased the model), which handles international artist and song names far better than a small offline model. The large Vosk model was tested and rejected (no grammar mode, 4.3 GB RAM, no accuracy gain)
5. **Fuzzy candidate selection**: accent-stripped `token_set_ratio` with the artist weighted 40%, alternatives tried in turn, and the user's own playlists searched before the catalogue
6. **No spoken announcement**: the music starting about 5 s after the command is the feedback; TTS is reserved for errors
7. **Graceful fallback**: control words from the transcript, one re-prompt, then regex parser on the local transcript only when Gemini is unavailable
8. **Scrobbling from the speaker's media status**: Last.fm only counts what the Chromecast actually played
9. **Spanish Model**: Spain variant (es-ES) for accurate recognition
10. **Modular Design**: Each component can be tested independently
11. **Config-Driven**: Easy to customize without code changes
12. **Service Mode**: systemd unit with journal and rotating file log, deployed with one command

## Dependencies Summary

### System Packages
- python3, python3-pip, python3-venv
- alsa-utils (arecord, amixer, alsactl)
- git, unzip, wget (utilities)
- ffmpeg (optional, for the test scripts)

### Python Packages
- vosk (wake word detection and local transcript)
- google-genai (Gemini command parsing)
- tidalapi (Tidal API)
- pychromecast (Chromecast)
- python-dotenv (config)
- requests
- g2p-en, fuzzywuzzy, nltk, python-Levenshtein (phonetic matching)
- gtts, pyttsx3 (text-to-speech)
- pylast (Last.fm scrobbling, optional)
- pytest (tests)

### External Assets
- vosk-model-small-es-0.42 (~58 MB on disk)
- Tidal subscription (required)
- Gemini API key (prepaid billing)

## Security Considerations

- **OAuth Tokens**: Never commit tidal_session.json (contains OAuth tokens) or lastfm_session.json
- **API keys**: `GEMINI_API_KEY` and the Last.fm keys live only in `.env` (gitignored)
- **Authentication**: OAuth device flow, no passwords stored
- **Privacy**: Wake word detection is fully offline; only the command audio after the wake word goes to Gemini
- **Network**: All devices must be on same WiFi
- **Permissions**: Service runs as user, not root

## Future Enhancements

See CLAUDE.md for detailed roadmap. Key items:
- Volume control via voice
- Web interface
- Multi-language (Catalan)
- Home Assistant integration
