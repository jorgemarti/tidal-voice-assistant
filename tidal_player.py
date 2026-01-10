"""
Tidal music player with Chromecast integration
"""

import tidalapi
from tidal_auth import load_tidal_session
import pychromecast
import time
import threading
import random
from phonetic_matcher import PhoneticMatcher
from tts_engine import get_tts_engine
from config import (
    CHROMECAST_NAME, TIDAL_CONFIG, setup_logging,
    RETRY_MAX_ATTEMPTS, RETRY_DELAY_SECONDS, RETRY_BACKOFF_MULTIPLIER,
    AUTOPLAY_ENABLED, AUTOPLAY_TRACK_COUNT,
    SEARCH_CACHE_ENABLED, SEARCH_CACHE_TTL, SEARCH_CACHE_MAX_SIZE,
    TTS_SHORT_ANNOUNCEMENTS
)

logger = setup_logging(__name__)


class SearchCache:
    """Simple TTL cache for Tidal search results."""

    def __init__(self, ttl: int = 300, max_size: int = 50):
        self.ttl = ttl
        self.max_size = max_size
        self._cache = {}  # key -> (timestamp, results)

    def _make_key(self, query: str, search_type: str) -> str:
        """Create cache key from query and search type."""
        return f"{search_type}:{query.lower().strip()}"

    def get(self, query: str, search_type: str):
        """Get cached results if valid."""
        key = self._make_key(query, search_type)
        if key in self._cache:
            timestamp, results = self._cache[key]
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit for: {query}")
                return results
            else:
                # Expired
                del self._cache[key]
        return None

    def set(self, query: str, search_type: str, results):
        """Store results in cache."""
        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        key = self._make_key(query, search_type)
        self._cache[key] = (time.time(), results)
        logger.debug(f"Cached results for: {query}")

# Audio cue URLs (from Google Actions sound library)
AUDIO_CUES = {
    'wake': "https://actions.google.com/sounds/v1/alarms/beep_short.ogg",
    'success': "https://actions.google.com/sounds/v1/cartoon/pop.ogg",
    'error': "https://actions.google.com/sounds/v1/cartoon/clang_and_wobble.ogg",
    'timeout': "https://actions.google.com/sounds/v1/cartoon/slide_whistle_to_drum.ogg",
}

# Backwards compatibility
ACTIVATION_SOUND_URL = AUDIO_CUES['wake']

class TidalPlayer:
    """
    Handles Tidal music search and playback via Chromecast.
    """

    def __init__(self, chromecast_name=None):
        """
        Initialize Tidal player.

        Args:
            chromecast_name: Name of Chromecast device (default: from config)
        """
        self.chromecast_name = chromecast_name or CHROMECAST_NAME
        self.session = None
        self.cast_device = None
        self.media_controller = None
        self.browser = None  # Store browser for cleanup
        self.phonetic_matcher = PhoneticMatcher()

        # Search cache
        self._search_cache = None
        if SEARCH_CACHE_ENABLED:
            self._search_cache = SearchCache(ttl=SEARCH_CACHE_TTL, max_size=SEARCH_CACHE_MAX_SIZE)

        # Load Tidal session
        logger.info("Loading Tidal session...")
        self.session = load_tidal_session()

        if not self.session:
            raise RuntimeError("Failed to load Tidal session")

        logger.info("Tidal session loaded successfully")

    def play_audio_cue(self, cue_type: str = 'wake'):
        """
        Play an audio cue on the Chromecast.

        Args:
            cue_type: Type of cue - 'wake', 'success', 'error', 'timeout'
        """
        if cue_type not in AUDIO_CUES:
            logger.warning(f"Unknown audio cue type: {cue_type}")
            cue_type = 'wake'

        logger.debug(f"Playing audio cue: {cue_type}")
        thread = threading.Thread(target=self._play_sound_async, args=(cue_type,))
        thread.daemon = True
        thread.start()

    def play_activation_sound(self):
        """
        Plays a short sound on the Chromecast to indicate the wake word was detected.
        Runs in a separate thread to be non-blocking.
        """
        self.play_audio_cue('wake')

    def _play_sound_async(self, cue_type: str = 'wake'):
        """Helper method to play sound without blocking."""
        try:
            if not self.cast_device and not self.find_chromecast():
                logger.error("Cannot play audio cue: Chromecast not found")
                return

            sound_url = AUDIO_CUES.get(cue_type, AUDIO_CUES['wake'])
            self.media_controller.play_media(sound_url, 'audio/ogg')
            logger.debug(f"Audio cue '{cue_type}' sent to Chromecast")

        except Exception as e:
            logger.error(f"Error playing audio cue: {e}")
    
    def find_chromecast(self, retry=True):
        """
        Find Chromecast device by name on local network with retry support.

        Args:
            retry: Whether to retry on failure (default: True)

        Returns:
            True if found, False otherwise
        """
        max_attempts = RETRY_MAX_ATTEMPTS if retry else 1
        delay = RETRY_DELAY_SECONDS

        for attempt in range(1, max_attempts + 1):
            logger.debug(f"Searching for Chromecast: '{self.chromecast_name}' (attempt {attempt}/{max_attempts})")

            try:
                # Stop any existing browser
                if self.browser:
                    self.browser.stop_discovery()

                chromecasts, self.browser = pychromecast.get_listed_chromecasts(
                    friendly_names=[self.chromecast_name]
                )

                if not chromecasts:
                    logger.warning(f"Chromecast '{self.chromecast_name}' not found")
                    if attempt < max_attempts:
                        logger.debug(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay *= RETRY_BACKOFF_MULTIPLIER
                        continue
                    else:
                        logger.error("Available devices:")
                        all_chromecasts, all_browser = pychromecast.get_chromecasts()
                        for cc in all_chromecasts:
                            logger.error(f"  - {cc.name} ({cc.model_name})")
                        all_browser.stop_discovery()
                        return False

                self.cast_device = chromecasts[0]
                self.cast_device.wait(timeout=10)
                self.media_controller = self.cast_device.media_controller

                logger.info(f"Connected to: {self.cast_device.name}")
                logger.debug(f"Model: {self.cast_device.model_name}, IP: {self.cast_device.cast_info.host}")

                return True

            except Exception as e:
                logger.error(f"Error finding Chromecast: {e}")
                if attempt < max_attempts:
                    logger.debug(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER
                else:
                    return False

        return False

    def cleanup(self):
        """Clean up resources"""
        if self.browser:
            self.browser.stop_discovery()
            self.browser = None
    
    def search_tidal(self, query, search_type='track', limit=5, retry=True):
        """
        Search Tidal for music with retry and cache support.

        Args:
            query: Search query string
            search_type: 'track', 'artist', or 'album'
            limit: Maximum number of results
            retry: Whether to retry on failure (default: True)

        Returns:
            List of search results or None
        """
        # Check cache first
        if self._search_cache:
            cached = self._search_cache.get(query, search_type)
            if cached is not None:
                return cached

        max_attempts = RETRY_MAX_ATTEMPTS if retry else 1
        delay = RETRY_DELAY_SECONDS

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(f"Searching Tidal for {search_type}: '{query}' (attempt {attempt}/{max_attempts})")
                search_result = self.session.search(query, limit=limit)

                # tidalapi 0.8+ returns a dict with 'tracks', 'artists', 'albums' keys
                results = None
                if search_type == 'track' and search_result.get('tracks'):
                    results = search_result['tracks']
                    logger.debug(f"Found {len(results)} tracks")
                elif search_type == 'artist' and search_result.get('artists'):
                    results = search_result['artists']
                    logger.debug(f"Found {len(results)} artists")
                elif search_type == 'album' and search_result.get('albums'):
                    results = search_result['albums']
                    logger.debug(f"Found {len(results)} albums")
                elif search_type == 'playlist' and search_result.get('playlists'):
                    results = search_result['playlists']
                    logger.debug(f"Found {len(results)} playlists")

                if results:
                    # Cache the results
                    if self._search_cache:
                        self._search_cache.set(query, search_type, results)
                    return results

                logger.warning(f"No {search_type} results found for: '{query}'")
                return None

            except Exception as e:
                logger.error(f"Tidal search error: {e}")
                if attempt < max_attempts:
                    logger.debug(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER
                else:
                    return None

        return None
    
    def play_track(self, track, retry=True, enqueue=False):
        """
        Play a single track on Chromecast with retry support.

        Args:
            track: Tidal track object
            retry: Whether to retry on failure (default: True)
            enqueue: If True, add to queue instead of playing immediately (default: False)

        Returns:
            True if successful, False otherwise
        """
        max_attempts = RETRY_MAX_ATTEMPTS if retry else 1
        delay = RETRY_DELAY_SECONDS

        action = "Queueing" if enqueue else "Playing"
        logger.info(f"{action}: {track.name} by {track.artist.name}")
        logger.debug(f"Album: {track.album.name}, Duration: {track.duration // 60}:{track.duration % 60:02d}")

        for attempt in range(1, max_attempts + 1):
            try:
                # Get stream URL
                stream_url = track.get_url()

                if not stream_url:
                    logger.error("Could not get stream URL")
                    return False

                # Cast to device
                self.media_controller.play_media(
                    stream_url,
                    'audio/mp4',
                    title=track.name,
                    thumb=track.album.image(1280) if track.album else None,
                    enqueue=enqueue
                )

                # Only block for the first track (not enqueued ones)
                if not enqueue:
                    self.media_controller.block_until_active()
                    logger.info("Playback started successfully")
                else:
                    logger.debug(f"Track queued: {track.name}")

                return True

            except Exception as e:
                logger.error(f"{'Queue' if enqueue else 'Playback'} error: {e}")
                if attempt < max_attempts:
                    logger.debug(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER
                else:
                    return False

        return False
    
    def play_artist_top_tracks(self, artist, limit=20):
        """
        Play top tracks from an artist with continuous playback (randomized order).

        Args:
            artist: Tidal artist object
            limit: Number of tracks to queue

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Getting top tracks from: {artist.name}")
            top_tracks = artist.get_top_tracks(limit=limit)

            if not top_tracks:
                logger.warning("No tracks found for artist")
                return False

            # Randomize track order
            top_tracks = list(top_tracks)
            random.shuffle(top_tracks)

            logger.debug(f"Queueing {len(top_tracks)} shuffled tracks from {artist.name}")

            # Announce the first track
            first_track = top_tracks[0]
            self._announce_track(first_track)

            # Play first track, queue the rest
            for i, track in enumerate(top_tracks):
                success = self.play_track(track, enqueue=(i > 0))
                if not success and i == 0:
                    # If first track fails, abort
                    return False

            logger.debug(f"Queued {len(top_tracks)} tracks for continuous playback")
            return True

        except Exception as e:
            logger.error(f"Error playing artist: {e}")
            return False

    def play_album(self, album):
        """
        Play an album with continuous playback.

        Args:
            album: Tidal album object

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Playing album: {album.name} by {album.artist.name}")
            logger.debug(f"Album has {album.num_tracks} tracks")

            tracks = album.tracks()
            if not tracks:
                logger.warning("No tracks found in album")
                return False

            logger.debug(f"Queueing {len(tracks)} tracks from album: {album.name}")

            # Play first track, queue the rest
            for i, track in enumerate(tracks):
                success = self.play_track(track, enqueue=(i > 0))
                if not success and i == 0:
                    # If first track fails, abort
                    return False

            logger.debug(f"Queued {len(tracks)} tracks for continuous playback")
            return True

        except Exception as e:
            logger.error(f"Error playing album: {e}")
            return False

    def play_playlist(self, playlist):
        """
        Play a playlist with all its tracks.

        Args:
            playlist: Tidal playlist object

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Playing playlist: {playlist.name}")
            logger.debug(f"Playlist has {playlist.num_tracks} tracks")

            tracks = playlist.tracks()
            if not tracks:
                logger.warning("No tracks found in playlist")
                return False

            logger.debug(f"Queueing {len(tracks)} tracks from playlist: {playlist.name}")

            # Play first track, queue the rest
            for i, track in enumerate(tracks):
                success = self.play_track(track, enqueue=(i > 0))
                if not success and i == 0:
                    return False

            logger.debug(f"Queued {len(tracks)} tracks for continuous playback")
            return True

        except Exception as e:
            logger.error(f"Error playing playlist: {e}")
            return False

    def play_track_with_autoplay(self, track, autoplay=None):
        """
        Play a single track and queue similar tracks for continuous playback.

        Uses Tidal's track radio feature to find similar songs.

        Args:
            track: Tidal track object
            autoplay: Override autoplay setting (default: use config)

        Returns:
            True if successful, False otherwise
        """
        # Use config setting if not explicitly specified
        if autoplay is None:
            autoplay = AUTOPLAY_ENABLED

        try:
            # Play the requested track first
            if not self.play_track(track):
                return False

            # Queue similar tracks if autoplay is enabled
            if autoplay:
                logger.debug("Getting similar tracks for autoplay...")
                try:
                    radio_tracks = track.get_track_radio(limit=AUTOPLAY_TRACK_COUNT)

                    if radio_tracks:
                        logger.debug(f"Queueing {len(radio_tracks)} similar tracks")
                        for radio_track in radio_tracks:
                            self.play_track(radio_track, enqueue=True)
                        logger.debug(f"Autoplay enabled with {len(radio_tracks)} tracks queued")
                    else:
                        logger.warning("No similar tracks found for autoplay")

                except Exception as e:
                    logger.warning(f"Could not get radio tracks: {e}")
                    # Continue anyway - at least the main track is playing

            return True

        except Exception as e:
            logger.error(f"Error playing track with autoplay: {e}")
            return False

    def phonetic_search_and_play(self, query, search_type='track'):
        """
        Search Tidal, use phonetic matching to find the best result, and play it.
        This is a two-stage search:
        1. Broad search on Tidal using the (potentially flawed) transcribed query.
        2. Phonetic matching on the results to find the most likely candidate.

        Args:
            query: Search query from speech transcription
            search_type: 'track', 'artist', or 'album'

        Returns:
            True if successful, False otherwise
        """
        # Ensure Chromecast is connected
        if not self.cast_device and not self.find_chromecast():
            return False

        # Clear any existing queue before starting new playback
        self.clear_queue()

        # 1. Broad search on Tidal to get candidates
        # We get more results (limit=10) to have a good pool for phonetic matching
        results = self.search_tidal(query, search_type, limit=10)

        if not results:
            logger.warning(f"No results found for: '{query}'")
            # Maybe speak this to the user
            self.speak(f"No pude encontrar nada para {query}")
            return False

        # 2. Use phonetic matching to find the best candidate
        # Get a list of just the names from the result objects
        candidate_names = [r.name for r in results]
        
        # Find the best name using our matcher
        best_name = self.phonetic_matcher.find_best_match(query, candidate_names)

        if not best_name:
            # This shouldn't happen if results were found, but as a fallback...
            best_match_object = results[0]
        else:
            # Find the full object that corresponds to the best name
            # This is safer than relying on list indices
            best_match_object = next((r for r in results if r.name == best_name), results[0])

        logger.debug(f"Phonetic match selected: '{best_match_object.name}'")

        # 3. Announce and play the best-matched item
        if search_type == 'track':
            self._announce_track(best_match_object)
            return self.play_track_with_autoplay(best_match_object)
        elif search_type == 'artist':
            # Announcement happens inside play_artist_top_tracks after selecting first track
            return self.play_artist_top_tracks(best_match_object)
        elif search_type == 'album':
            self._announce_album(best_match_object)
            return self.play_album(best_match_object)
        elif search_type == 'playlist':
            self._announce_playlist(best_match_object)
            return self.play_playlist(best_match_object)

        return False

    def search_and_play(self, query, search_type='track'):
        """
        Search Tidal and play the best match.

        Args:
            query: Search query
            search_type: 'track', 'artist', or 'album'

        Returns:
            True if successful, False otherwise
        """
        # Ensure Chromecast is connected
        if not self.cast_device and not self.find_chromecast():
            return False

        # Clear any existing queue before starting new playback
        self.clear_queue()

        # Search Tidal
        results = self.search_tidal(query, search_type)

        if not results:
            logger.warning(f"No results found for: '{query}'")
            return False

        # Play based on search type
        if search_type == 'track':
            return self.play_track_with_autoplay(results[0])
        elif search_type == 'artist':
            return self.play_artist_top_tracks(results[0])
        elif search_type == 'album':
            return self.play_album(results[0])
        elif search_type == 'playlist':
            return self.play_playlist(results[0])

        return False

    def _announce_track(self, track):
        """Announce a track with optional short mode."""
        if TTS_SHORT_ANNOUNCEMENTS:
            self.speak(track.name)
        else:
            self.speak(f"Reproduciendo {track.name} de {track.artist.name}.")

    def _announce_album(self, album):
        """Announce an album with optional short mode."""
        if TTS_SHORT_ANNOUNCEMENTS:
            self.speak(album.name)
        else:
            self.speak(f"Reproduciendo el álbum {album.name} de {album.artist.name}.")

    def _announce_playlist(self, playlist):
        """Announce a playlist with optional short mode."""
        if TTS_SHORT_ANNOUNCEMENTS:
            self.speak(playlist.name)
        else:
            self.speak(f"Reproduciendo la playlist {playlist.name}.")

    def speak(self, message, lang='es', wait=True):
        """
        Speak a message on the Chromecast using TTS engine.

        Uses local TTS (pyttsx3) or Google TTS based on config.

        Args:
            message: Text to speak
            lang: Language code (default: 'es' for Spanish)
            wait: Wait for speech to complete before returning (default: True)
        """
        if not self.cast_device and not self.find_chromecast():
            logger.error("Cannot speak: Chromecast not found")
            return False

        try:
            tts_engine = get_tts_engine()
            tts_url = tts_engine.get_tts_url(message, lang)

            logger.debug(f"Speaking: {message}")
            self.media_controller.play_media(tts_url, 'audio/mp3')

            # Wait for media to start
            try:
                self.media_controller.block_until_active(timeout=5)
            except Exception as e:
                logger.warning(f"block_until_active failed: {e}")

            if wait:
                # First, wait for playback to actually START
                max_start_wait = 3
                started = False
                for _ in range(int(max_start_wait / 0.2)):
                    time.sleep(0.2)
                    self.media_controller.update_status()
                    status = self.media_controller.status
                    if status and status.player_state == 'PLAYING':
                        started = True
                        logger.debug("TTS playback started")
                        break

                if not started:
                    # Fallback: estimate duration based on text length
                    wait_time = max(2.0, len(message) * 0.08 + 1.0)
                    logger.debug(f"TTS status unknown, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                else:
                    # Poll until media stops playing
                    max_wait = 15
                    waited = 0
                    poll_interval = 0.25

                    while waited < max_wait:
                        time.sleep(poll_interval)
                        waited += poll_interval

                        self.media_controller.update_status()
                        status = self.media_controller.status

                        if status is None:
                            break

                        # Check if playback finished
                        if status.player_state in ('IDLE', 'UNKNOWN'):
                            logger.debug(f"TTS finished (state: {status.player_state})")
                            break

                # Buffer after completion
                time.sleep(0.5)

            return True
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False

    def stop(self):
        """Stop playback and clear queue"""
        if self.media_controller:
            try:
                # Stop current playback
                self.media_controller.stop()
                # Give time for stop to take effect
                time.sleep(0.3)
                # Launch default media receiver to clear any queue
                if self.cast_device:
                    self.cast_device.quit_app()
                    time.sleep(0.2)
                logger.info("Playback stopped and queue cleared")
            except Exception as e:
                logger.error(f"Error stopping playback: {e}")

    def clear_queue(self):
        """Clear the playback queue without stopping current track"""
        if self.cast_device:
            try:
                # Quit and reconnect to clear queue
                self.cast_device.quit_app()
                time.sleep(0.3)
                logger.debug("Queue cleared")
            except Exception as e:
                logger.error(f"Error clearing queue: {e}")

    def pause(self):
        """Pause playback"""
        if self.media_controller:
            self.media_controller.pause()
            logger.info("Playback paused")

    def play(self):
        """Resume playback"""
        if not self.cast_device:
            logger.warning("Cannot resume: Chromecast not connected")
            return False
        if self.media_controller:
            try:
                self.media_controller.play()
                logger.info("Playback resumed")
                return True
            except Exception as e:
                logger.error(f"Resume failed: {e}")
                return False
        return False

    def skip(self):
        """Skip to next track in queue"""
        if self.media_controller:
            self.media_controller.queue_next()
            logger.info("Skipped to next track")

    def is_playing(self):
        """Check if music is currently playing or paused (active session)"""
        if not self.media_controller:
            return False
        try:
            self.media_controller.update_status()
            status = self.media_controller.status
            if status and status.player_state in ('PLAYING', 'PAUSED', 'BUFFERING'):
                return True
        except Exception as e:
            logger.debug(f"Error checking playback status: {e}")
        return False

if __name__ == "__main__":
    """Test Tidal player"""
    import sys
    
    print("=" * 60)
    print("Tidal Player Test")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        print("Usage: python tidal_player.py <search_query> [track|artist|album]")
        print()
        print("Examples:")
        print("  python tidal_player.py 'bohemian rhapsody' track")
        print("  python tidal_player.py 'queen' artist")
        print("  python tidal_player.py 'a night at the opera' album")
        sys.exit(1)
    
    query = sys.argv[1]
    search_type = sys.argv[2] if len(sys.argv) > 2 else 'track'
    
    try:
        player = TidalPlayer()
        success = player.search_and_play(query, search_type)
        
        if success:
            print()
            print("✅ Playing... Press Ctrl+C to stop")
            while True:
                time.sleep(1)
        else:
            print("\n❌ Playback failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping playback...")
        player.stop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
