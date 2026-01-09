# Alternative Speech Recognition Architecture

## Current Problem

Vosk works reasonably well for wake word detection (limited vocabulary, local), but performs poorly for:
- Command recognition ("reproduce", "pon música de")
- Artist names (especially non-Spanish: "Queen", "Metallica", "Coldplay")
- Song and album names (mixed languages)

The core issue: Vosk's small Spanish model lacks vocabulary for international artist/song names and struggles with accented speech patterns.

## Proposed Solution: Hybrid Architecture

**Keep Vosk for wake word detection, use cloud speech recognition for commands.**

```
┌─────────────────────────────────────────────────────────────────┐
│                        HYBRID ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [Microphone] ──► [Vosk - Local]                               │
│                         │                                        │
│                         ▼                                        │
│                   Wake word detected?                            │
│                    /            \                                │
│                  No              Yes                             │
│                   │               │                              │
│                   ▼               ▼                              │
│              Continue         Record 5-8s                        │
│              listening        of audio                           │
│                                   │                              │
│                                   ▼                              │
│                         [Google Speech API]  ◄── Cloud (free)    │
│                                   │                              │
│                                   ▼                              │
│                          Transcribed text                        │
│                          (high accuracy)                         │
│                                   │                              │
│                                   ▼                              │
│                         [Command Parser]                         │
│                                   │                              │
│                                   ▼                              │
│                         [Tidal Player]                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Options Comparison

| Solution | Latency | Cost | Accuracy | Offline | Implementation |
|----------|---------|------|----------|---------|----------------|
| **Google Speech (SpeechRecognition)** | 1-2s | Free | Excellent | No | Easy |
| Google Cloud Speech-to-Text | 1-2s | $0.006/15s | Excellent | No | Medium |
| OpenAI Whisper API | 2-4s | $0.006/min | Excellent | No | Easy |
| Local Whisper (faster-whisper) | 4-10s* | Free | Very Good | Yes | Medium |
| Vosk Large Model | 0.5-1s | Free | Mediocre | Yes | Easy |

*Pi 5 with tiny/base model

## Recommended: Google Speech Recognition

Using the `speech_recognition` Python library with Google's free web API:

### Advantages
- **Free**: No API key required, uses Google's public endpoint
- **Fast**: 1-2 second latency
- **Accurate**: Handles Spanish commands + international artist names
- **Simple**: Drop-in replacement, ~50 lines of code
- **Multilingual**: Automatically handles mixed-language queries

### Disadvantages
- Requires internet for command recognition (wake word still works offline)
- May have rate limits under heavy use (unlikely for personal use)
- Privacy: Audio sent to Google (only after wake word)

### Implementation

```python
# New file: cloud_recognizer.py
import speech_recognition as sr
from config import setup_logging

logger = setup_logging(__name__)

class CloudRecognizer:
    """Cloud-based speech recognition for commands."""

    def __init__(self, language='es-ES'):
        self.recognizer = sr.Recognizer()
        self.language = language
        # Adjust for ambient noise sensitivity
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300

    def recognize_from_audio_data(self, audio_data, sample_rate=16000):
        """
        Recognize speech from raw audio bytes.

        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            sample_rate: Audio sample rate

        Returns:
            Tuple of (text, confidence) or (None, 0) on failure
        """
        try:
            # Convert raw audio to AudioData object
            audio = sr.AudioData(audio_data, sample_rate, 2)  # 2 = sample width (16-bit)

            # Use Google's free speech recognition
            # Returns multiple alternatives with show_all=True
            result = self.recognizer.recognize_google(
                audio,
                language=self.language,
                show_all=True
            )

            if not result:
                return None, 0

            # Extract best result
            if isinstance(result, dict) and 'alternative' in result:
                alternatives = result['alternative']
                if alternatives:
                    best = alternatives[0]
                    text = best.get('transcript', '')
                    confidence = best.get('confidence', 0.8)
                    logger.info(f"Google recognized: '{text}' (confidence: {confidence:.2f})")
                    return text, confidence

            # Simple string result
            if isinstance(result, str):
                return result, 0.8

            return None, 0

        except sr.UnknownValueError:
            logger.warning("Google could not understand audio")
            return None, 0
        except sr.RequestError as e:
            logger.error(f"Google API error: {e}")
            return None, 0
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return None, 0

    def recognize_from_microphone(self, timeout=5, phrase_time_limit=8):
        """
        Record from microphone and recognize.

        Args:
            timeout: Max seconds to wait for speech to start
            phrase_time_limit: Max seconds of speech to record

        Returns:
            Recognized text or None
        """
        try:
            with sr.Microphone() as source:
                logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                logger.info("Listening for command...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )

                text = self.recognizer.recognize_google(audio, language=self.language)
                logger.info(f"Recognized: {text}")
                return text

        except sr.WaitTimeout:
            logger.warning("Listening timed out")
            return None
        except Exception as e:
            logger.error(f"Microphone error: {e}")
            return None
```

### Integration with AudioProcessor

Modify `audio_processor.py` to use cloud recognition after wake word:

```python
# In AudioProcessor.__init__
from cloud_recognizer import CloudRecognizer
self.cloud_recognizer = CloudRecognizer(language='es-ES')

# In the command listening phase, instead of using Vosk:
def _process_command_audio(self, audio_buffer):
    """Process recorded audio through cloud recognition."""
    # Convert audio buffer to bytes
    audio_bytes = b''.join(audio_buffer)

    # Use Google for accurate recognition
    text, confidence = self.cloud_recognizer.recognize_from_audio_data(
        audio_bytes,
        sample_rate=SAMPLE_RATE
    )

    if text and confidence > 0.5:
        return [text]  # Return as list for compatibility
    return []
```

## Performance Optimization

### 1. Parallel Processing
Start cloud recognition while still recording the tail of audio:

```python
import concurrent.futures

executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

def recognize_async(audio_data):
    future = executor.submit(cloud_recognizer.recognize_from_audio_data, audio_data)
    return future  # Call future.result() when needed
```

### 2. Audio Streaming (Advanced)
For lowest latency, stream audio to Google Cloud Speech-to-Text (requires API key):

```python
# Streaming recognition - results arrive as user speaks
# Adds ~$0.006/15s but reduces perceived latency by 50%
```

### 3. Caching Common Queries
Cache phonetic matches for frequently requested artists:

```python
# LRU cache for artist name resolution
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_artist_search(query):
    return tidal.search(query, 'artist')
```

## Timeline Comparison

### Current (Vosk only)
```
Wake word ──► Vosk transcribe (1s) ──► Parse ──► Search ──► Play
Total: ~3-5s, but often FAILS due to poor transcription
```

### Proposed (Hybrid)
```
Wake word ──► Record (2s) ──► Google API (1.5s) ──► Parse ──► Search ──► Play
Total: ~4-6s, with HIGH SUCCESS RATE
```

The extra 1-2 seconds is negligible compared to the frustration of failed recognition.

## Alternative: Local Whisper

For fully offline operation, use `faster-whisper` with the `tiny` or `base` model:

```python
from faster_whisper import WhisperModel

# Load once at startup (uses ~500MB RAM for tiny model)
model = WhisperModel("tiny", device="cpu", compute_type="int8")

def transcribe_local(audio_path):
    segments, info = model.transcribe(audio_path, language="es")
    return " ".join([s.text for s in segments])
```

**Performance on Pi 5:**
- `tiny` model: 4-6s for 5s audio
- `base` model: 8-12s for 5s audio

This is slower but works without internet.

## Recommendation

1. **Phase 1**: Implement Google Speech Recognition (free, fast, accurate)
2. **Phase 2**: Add Whisper as fallback when offline
3. **Phase 3** (optional): Migrate to Google Cloud Speech-to-Text for streaming

## Required Changes

1. Add `SpeechRecognition` to requirements.txt:
   ```
   SpeechRecognition>=3.10.0
   ```

2. Create `cloud_recognizer.py` (as shown above)

3. Modify `audio_processor.py`:
   - Keep Vosk for wake word detection
   - After wake word, record raw audio to buffer
   - Send buffer to CloudRecognizer instead of Vosk

4. Update `config.py`:
   ```python
   # Speech Recognition Configuration
   COMMAND_RECOGNITION = 'google'  # 'google', 'whisper', 'vosk'
   COMMAND_LANGUAGE = 'es-ES'
   COMMAND_TIMEOUT = 8  # seconds
   ```

## Estimated Implementation Time

- Cloud recognizer module: 1 hour
- AudioProcessor integration: 2 hours
- Testing and tuning: 2 hours
- **Total: ~5 hours**

## Conclusion

The hybrid approach (Vosk wake word + Google command recognition) provides:
- **Best accuracy** for artist/song names
- **Minimal latency** increase (~1.5s)
- **Zero cost** (free Google API)
- **Simple implementation** (speech_recognition library)
- **Graceful degradation** (wake word still works offline)

This solves the core problem: Vosk's poor vocabulary for music-related queries, while keeping the system responsive and free.
