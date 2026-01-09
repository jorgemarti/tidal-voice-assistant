"""
Cloud-based speech recognition for command processing.

Uses Google Speech Recognition (free) for accurate transcription of
commands, artist names, and song titles after wake word detection.
"""

import speech_recognition as sr
from config import setup_logging, COMMAND_LANGUAGE

logger = setup_logging(__name__)


class CloudRecognizer:
    """
    Cloud-based speech recognition using Google's free API.

    Provides high-accuracy transcription for music commands,
    artist names, and song titles in Spanish with support for
    international artist/song names.
    """

    def __init__(self, language=None):
        """
        Initialize the cloud recognizer.

        Args:
            language: Language code (default: from config, e.g., 'es-ES')
        """
        self.recognizer = sr.Recognizer()
        self.language = language or COMMAND_LANGUAGE

        # Adjust recognition settings
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8  # Seconds of silence to consider phrase complete

        logger.debug(f"Cloud recognizer initialized (language: {self.language})")

    def recognize_from_audio_data(self, audio_data, sample_rate=16000, sample_width=2):
        """
        Recognize speech from raw audio bytes using Google Speech API.

        Args:
            audio_data: Raw audio bytes (PCM format)
            sample_rate: Audio sample rate in Hz
            sample_width: Sample width in bytes (2 for 16-bit audio)

        Returns:
            List of transcription alternatives (best first), or empty list on failure
        """
        try:
            # Convert raw audio to AudioData object
            audio = sr.AudioData(audio_data, sample_rate, sample_width)

            # Use Google's free speech recognition with alternatives
            result = self.recognizer.recognize_google(
                audio,
                language=self.language,
                show_all=True
            )

            if not result:
                logger.warning("Google returned no results")
                return []

            # Extract alternatives from result
            alternatives = []

            if isinstance(result, dict) and 'alternative' in result:
                for alt in result['alternative']:
                    transcript = alt.get('transcript', '').strip()
                    if transcript:
                        confidence = alt.get('confidence', 0.0)
                        alternatives.append(transcript)
                        logger.debug(f"Alternative: '{transcript}' (confidence: {confidence:.2f})")

                if alternatives:
                    logger.debug(f"Google recognized: '{alternatives[0]}'")

            elif isinstance(result, str):
                # Simple string result (older API response)
                alternatives = [result.strip()]
                logger.debug(f"Google recognized: '{result}'")

            return alternatives

        except sr.UnknownValueError:
            logger.warning("Google could not understand audio")
            return []
        except sr.RequestError as e:
            logger.error(f"Google API request error: {e}")
            return []
        except Exception as e:
            logger.error(f"Cloud recognition error: {e}")
            return []

    def recognize_from_microphone(self, device_index=None, timeout=5, phrase_time_limit=8):
        """
        Record from microphone and recognize speech.

        This is a convenience method for testing. The main application
        uses recognize_from_audio_data with audio from AudioProcessor.

        Args:
            device_index: Microphone device index (None for default)
            timeout: Max seconds to wait for speech to start
            phrase_time_limit: Max seconds of speech to record

        Returns:
            Recognized text or None
        """
        try:
            mic_kwargs = {}
            if device_index is not None:
                mic_kwargs['device_index'] = device_index

            with sr.Microphone(**mic_kwargs) as source:
                logger.debug("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                logger.debug("Listening for command...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )

                text = self.recognizer.recognize_google(
                    audio,
                    language=self.language
                )
                logger.debug(f"Recognized: {text}")
                return text

        except sr.WaitTimeout:
            logger.warning("Listening timed out - no speech detected")
            return None
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Microphone recognition error: {e}")
            return None


# Test function
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Cloud Speech Recognition Test")
    print("=" * 60)
    print()

    recognizer = CloudRecognizer()

    # Get device index from command line or use default
    device_index = int(sys.argv[1]) if len(sys.argv) > 1 else None

    print(f"Using microphone device: {device_index or 'default'}")
    print("Speak a command (e.g., 'reproduce música de Queen')...")
    print()

    result = recognizer.recognize_from_microphone(
        device_index=device_index,
        timeout=5,
        phrase_time_limit=8
    )

    if result:
        print(f"\nRecognized: {result}")
    else:
        print("\nNo speech recognized")
