"""
Tidal music player with Chromecast integration
"""

import tidalapi
from tidal_auth import load_tidal_session
import pychromecast
import time
from config import CHROMECAST_NAME, TIDAL_CONFIG

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
        
        # Load Tidal session
        print("Loading Tidal session...")
        self.session = load_tidal_session()
        
        if not self.session:
            raise RuntimeError("Failed to load Tidal session")
        
        print("✅ Tidal session loaded")
    
    def find_chromecast(self):
        """
        Find Chromecast device by name on local network.
        
        Returns:
            True if found, False otherwise
        """
        print(f"Searching for Chromecast: '{self.chromecast_name}'...")
        
        try:
            chromecasts, browser = pychromecast.get_listed_chromecasts(
                friendly_names=[self.chromecast_name]
            )
            
            if not chromecasts:
                print(f"❌ Chromecast '{self.chromecast_name}' not found")
                print("Available devices:")
                all_chromecasts, _ = pychromecast.get_chromecasts()
                for cc in all_chromecasts:
                    print(f"  - {cc.name} ({cc.model_name})")
                return False
            
            self.cast_device = chromecasts[0]
            self.cast_device.wait()
            self.media_controller = self.cast_device.media_controller

            print(f"✅ Connected to: {self.cast_device.name}")
            print(f"   Model: {self.cast_device.model_name}")
            print(f"   IP: {self.cast_device.cast_info.host}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error finding Chromecast: {e}")
            return False
    
    def search_tidal(self, query, search_type='track', limit=5):
        """
        Search Tidal for music.
        
        Args:
            query: Search query string
            search_type: 'track', 'artist', or 'album'
            limit: Maximum number of results
            
        Returns:
            List of search results or None
        """
        try:
            print(f"🔍 Searching Tidal for {search_type}: '{query}'")
            search_result = self.session.search(query, limit=limit)
            
            if search_type == 'track' and search_result.tracks:
                return search_result.tracks
            elif search_type == 'artist' and search_result.artists:
                return search_result.artists
            elif search_type == 'album' and search_result.albums:
                return search_result.albums
            
            return None
            
        except Exception as e:
            print(f"❌ Tidal search error: {e}")
            return None
    
    def play_track(self, track):
        """
        Play a single track on Chromecast.
        
        Args:
            track: Tidal track object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"▶️  Playing: {track.name}")
            print(f"   Artist: {track.artist.name}")
            print(f"   Album: {track.album.name}")
            print(f"   Duration: {track.duration // 60}:{track.duration % 60:02d}")
            
            # Get stream URL
            stream_url = track.get_url()
            
            if not stream_url:
                print("❌ Could not get stream URL")
                return False
            
            # Cast to device
            self.media_controller.play_media(
                stream_url,
                'audio/mp4',
                title=track.name,
                thumb=track.album.image(1280) if track.album else None
            )
            self.media_controller.block_until_active()
            
            print("✅ Playback started")
            return True
            
        except Exception as e:
            print(f"❌ Playback error: {e}")
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
            print(f"🎵 Getting top tracks from: {artist.name}")
            top_tracks = artist.get_top_tracks(limit=limit)
            
            if not top_tracks:
                print("❌ No tracks found")
                return False
            
            # Play first track
            return self.play_track(top_tracks[0])
            
        except Exception as e:
            print(f"❌ Error playing artist: {e}")
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
            print(f"💿 Playing album: {album.name}")
            print(f"   Artist: {album.artist.name}")
            print(f"   Tracks: {album.num_tracks}")
            
            tracks = album.tracks()
            if not tracks:
                print("❌ No tracks found in album")
                return False
            
            # Play first track
            return self.play_track(tracks[0])
            
        except Exception as e:
            print(f"❌ Error playing album: {e}")
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
            print(f"❌ No results found for: '{query}'")
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
            print("⏹️  Playback stopped")
    
    def pause(self):
        """Pause playback"""
        if self.media_controller:
            self.media_controller.pause()
            print("⏸️  Playback paused")
    
    def play(self):
        """Resume playback"""
        if self.media_controller:
            self.media_controller.play()
            print("▶️  Playback resumed")

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
