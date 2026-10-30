# Improvement Ideas

Future enhancements for the Tidal Voice Assistant, organized by category.

## Completed

| # | Improvement | Status |
|---|-------------|--------|
| 1 | **VAD (Voice Activity Detection)** | ✅ Implemented: energy-based end of speech in `audio_processor.py` (RMS over a tracked noise floor) |
| 2 | **Pre-connect to Chromecast** | ✅ Implemented: connects on startup |
| 3 | **Local TTS** | ✅ Implemented: pyttsx3 support with Google fallback |
| 4 | **Search cache** | ✅ Implemented: TTL cache for Tidal searches |
| 6 | **Short announcement mode** | ✅ Implemented: `TTS_SHORT_ANNOUNCEMENTS`; playback announcements are now off altogether (`TTS_ANNOUNCE_PLAYBACK = False`) |
| 7 | **Distinct audio cues** | ✅ Implemented: different sounds for wake/success/error/timeout (only the wake cue plays unless `PLAYBACK_CUES`) |
| 12 | **Configurable wake word** | ✅ Implemented: `WAKE_WORDS` list (Vosk grammar mode) |
| 16 | **Unit tests** | ✅ Implemented: pytest tests for command_parser, phonetic_matcher, lastfm_scrobbler |
| 17 | **Type hints** | ✅ Implemented: added to command_parser.py |
| 18 | **Retry decorator** | ✅ Implemented: `@with_retry` in utils.py |
| 11 | **Graceful speech fallback** | ✅ Implemented: Gemini `unknown` falls back to control words from the Vosk transcript or one re-prompt; regex parser when Gemini is unavailable |
| 20 | **Last.fm scrobbling** | ✅ Implemented: `lastfm_scrobbler.py` from the Chromecast media status |
| 21 | **Versioning and deployment** | ✅ Implemented: `VERSION`, `deploy.sh`, rotating log file |

## Remaining - UX (User Experience)

| # | Improvement | Description |
|---|-------------|-------------|
| 5 | **"What's playing?" command** | Add "¿Qué suena?" or "¿Qué estás poniendo?" to announce current track and artist. |
| 8 | **Volume control** | Add voice commands: "sube el volumen", "baja el volumen", "volumen al 50%". |
| 9 | **Shuffle mode toggle** | Add "mezcla" or "aleatorio" command to toggle shuffle for artist/playlist playback. |
| 10 | **Repeat command** | Add "repite" to replay current track, or "otra vez" to repeat last search. |

## Remaining - Usability

| # | Improvement | Description |
|---|-------------|-------------|
| 13 | **Status LED support** | Use Raspberry Pi GPIO to drive an LED: off=idle, blinking=listening, solid=processing. |
| 14 | **Health check endpoint** | Simple HTTP server (port 8080) returning JSON status for monitoring/Home Assistant integration. |
| 15 | **Favorites/shortcuts** | Voice shortcuts like "pon mi música" to play a configured default playlist or artist. |

## Remaining - Code Quality

| # | Improvement | Description |
|---|-------------|-------------|
| 19 | **Async refactor** | Convert to asyncio for non-blocking Chromecast/Tidal operations. (Deferred - requires architectural changes) |

## Quick Wins (Recommended Next Steps)

1. **#5**: "What's playing?" command (useful feature, easy to implement)
2. **#8**: volume control (commonly requested)
3. **#14**: health check endpoint (useful once Home Assistant comes in)

*To implement an idea, reference it by number (e.g., "implement #5").*
