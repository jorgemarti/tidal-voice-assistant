"""
Tidal music player with Chromecast integration
"""

import tidalapi
from tidal_auth import load_tidal_session
import pychromecast
import time
from config import (
    CHROMECAST_NAME, TIDAL_CONFIG, setup_logging,
    RETRY_MAX_ATTEMPTS, RETRY_DELAY_SECONDS, RETRY_BACKOFF_MULTIPLIER
)

logger = setup_logging(__name__)

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

        # Load Tidal session
        logger.info("Loading Tidal session...")
        self.session = load_tidal_session()

        if not self.session:
            raise RuntimeError("Failed to load Tidal session")

        logger.info("Tidal session loaded successfully")
    
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
            logger.info(f"Searching for Chromecast: '{self.chromecast_name}' (attempt {attempt}/{max_attempts})")

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
                        logger.info(f"Retrying in {delay} seconds...")
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
                    logger.info(f"Retrying in {delay} seconds...")
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
        Search Tidal for music with retry support.

        Args:
            query: Search query string
            search_type: 'track', 'artist', or 'album'
            limit: Maximum number of results
            retry: Whether to retry on failure (default: True)

        Returns:
            List of search results or None
        """
        max_attempts = RETRY_MAX_ATTEMPTS if retry else 1
        delay = RETRY_DELAY_SECONDS

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Searching Tidal for {search_type}: '{query}' (attempt {attempt}/{max_attempts})")
                search_result = self.session.search(query, limit=limit)

                # tidalapi 0.8+ returns a dict with 'tracks', 'artists', 'albums' keys
                if search_type == 'track' and search_result.get('tracks'):
                    tracks = search_result['tracks']
                    logger.debug(f"Found {len(tracks)} tracks")
                    return tracks
                elif search_type == 'artist' and search_result.get('artists'):
                    artists = search_result['artists']
                    logger.debug(f"Found {len(artists)} artists")
                    return artists
                elif search_type == 'album' and search_result.get('albums'):
                    albums = search_result['albums']
                    logger.debug(f"Found {len(albums)} albums")
                    return albums

                logger.warning(f"No {search_type} results found for: '{query}'")
                return None

            except Exception as e:
                logger.error(f"Tidal search error: {e}")
                if attempt < max_attempts:
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER
                else:
                    return None

        return None
    
    def play_track(self, track, retry=True):
        """
        Play a single track on Chromecast with retry support.

        Args:
            track: Tidal track object
            retry: Whether to retry on failure (default: True)

        Returns:
            True if successful, False otherwise
        """
        max_attempts = RETRY_MAX_ATTEMPTS if retry else 1
        delay = RETRY_DELAY_SECONDS

        logger.info(f"Playing: {track.name} by {track.artist.name}")
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
                    thumb=track.album.image(1280) if track.album else None
                )
                self.media_controller.block_until_active()

                logger.info("Playback started successfully")
                return True

            except Exception as e:
                logger.error(f"Playback error: {e}")
                if attempt < max_attempts:
                    logger.info(f"Retrying playback in {delay} seconds...")
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER
                else:
                    return False

        return False
    
    def play_artist_top_tracks(self, artist, limit=20):
        """
        Play top tracks from an artist.

        Args:
            artist: Tidal artist object
            limit: Number of tracks to queue

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Getting top tracks from: {artist.name}")
            top_tracks = artist.get_top_tracks(limit=limit)

            if not top_tracks:
                logger.warning("No tracks found for artist")
                return False

            # Play first track
            return self.play_track(top_tracks[0])

        except Exception as e:
            logger.error(f"Error playing artist: {e}")
            return False

    def play_album(self, album):
        """
        Play an album.

        Args:
            album: Tidal album object

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Playing album: {album.name} by {album.artist.name}")
            logger.debug(f"Album has {album.num_tracks} tracks")

            tracks = album.tracks()
            if not tracks:
                logger.warning("No tracks found in album")
                return False

            # Play first track
            return self.play_track(tracks[0])

        except Exception as e:
            logger.error(f"Error playing album: {e}")
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

        # Search Tidal
        results = self.search_tidal(query, search_type)

        if not results:
            logger.warning(f"No results found for: '{query}'")
            return False

        # Play based on search type
        if search_type == 'track':
            return self.play_track(results[0])
        elif search_type == 'artist':
            return self.play_artist_top_tracks(results[0])
        elif search_type == 'album':
            return self.play_album(results[0])

        return False

    def stop(self):
        """Stop playback"""
        if self.media_controller:
            self.media_controller.stop()
            logger.info("Playback stopped")

    def pause(self):
        """Pause playback"""
        if self.media_controller:
            self.media_controller.pause()
            logger.info("Playback paused")

    def play(self):
        """Resume playback"""
        if self.media_controller:
            self.media_controller.play()
            logger.info("Playback resumed")

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
