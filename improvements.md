# Improvement Ideas

Future enhancements for the Tidal Voice Assistant, organized by category.

## Performance

| # | Improvement | Impact | Complexity | Description |
|---|-------------|--------|------------|-------------|
| 1 | **Add VAD (Voice Activity Detection)** | High | Medium | Add webrtcvad or silero-vad before Vosk to only process audio when speech is detected. Could reduce CPU from ~20% to ~5%. |
| 2 | **Pre-connect to Chromecast on startup** | Medium | Low | Connect to Chromecast during initialization instead of on first command. Reduces first-command latency by ~2-3 seconds. |
| 3 | **Use local TTS** | Medium | Low | Replace Google Translate TTS with pyttsx3 or espeak. Faster response, works offline, no network dependency. |
| 4 | **Cache Tidal search results** | Low | Low | Cache recent searches in memory to avoid repeated API calls for the same query. |

## UX (User Experience)

| # | Improvement | Description |
|---|-------------|-------------|
| 5 | **"What's playing?" command** | Add "¿Qué suena?" or "¿Qué estás poniendo?" to announce current track and artist. |
| 6 | **Shorter announcement mode** | Config option for brief announcements: just "Bohemian Rhapsody" instead of "Reproduciendo Bohemian Rhapsody de Queen". |
| 7 | **Distinct audio cues** | Different beeps/sounds for: wake word detected, command success, error, timeout. Currently only one beep. |
| 8 | **Volume control** | Add voice commands: "sube el volumen", "baja el volumen", "volumen al 50%". |
| 9 | **Shuffle mode toggle** | Add "mezcla" or "aleatorio" command to toggle shuffle for artist/playlist playback. |
| 10 | **Repeat command** | Add "repite" to replay current track, or "otra vez" to repeat last search. |

## Usability

| # | Improvement | Description |
|---|-------------|-------------|
| 11 | **Graceful speech API fallback** | If Google Speech fails, silently fall back to Vosk without user-visible errors. |
| 12 | **Configurable wake word** | Move wake word patterns to config.py instead of hardcoded regex. Allow custom wake phrases. |
| 13 | **Status LED support** | Use Raspberry Pi GPIO to drive an LED: off=idle, blinking=listening, solid=processing. |
| 14 | **Health check endpoint** | Simple HTTP server (port 8080) returning JSON status for monitoring/Home Assistant integration. |
| 15 | **Favorites/shortcuts** | Voice shortcuts like "pon mi música" to play a configured default playlist or artist. |

## Code Quality

| # | Improvement | Description |
|---|-------------|-------------|
| 16 | **Add unit tests** | pytest tests for command_parser.py and phonetic_matcher.py to prevent regressions. |
| 17 | **Type hints** | Add Python type hints throughout codebase for better IDE support and fewer bugs. |
| 18 | **Retry decorator** | Create a `@with_retry` decorator to replace repeated retry logic in tidal_player.py. |
| 19 | **Async refactor** | Convert to asyncio for non-blocking Chromecast/Tidal operations. |

## Quick Wins (High Impact, Low Effort)

Recommended starting points:
- **#2** - Pre-connect Chromecast (simple code change, noticeable improvement)
- **#5** - "What's playing?" command (useful feature, easy to implement)
- **#3** - Local TTS (removes network dependency for announcements)
- **#7** - Distinct audio cues (better user feedback)

---

*To implement an idea, reference it by number (e.g., "implement #5").*
