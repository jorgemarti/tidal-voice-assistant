#!/usr/bin/env python3
"""
Test Tidal integration and playback
"""

import sys
from tidal_player import TidalPlayer
import time

def test_tidal_search(query, search_type='track'):
    """Test Tidal search functionality"""
    print("=" * 60)
    print(f"Tidal Search Test: {search_type}")
    print("=" * 60)
    print()
    print(f"Query: '{query}'")
    print()
    
    try:
        player = TidalPlayer()
        results = player.search_tidal(query, search_type, limit=5)
        
        if not results:
            print("❌ No results found")
            return False
        
        print(f"✅ Found {len(results)} result(s):")
        print()
        
        for i, item in enumerate(results, 1):
            if search_type == 'track':
                print(f"{i}. {item.name}")
                print(f"   Artist: {item.artist.name}")
                print(f"   Album: {item.album.name}")
                print(f"   Duration: {item.duration // 60}:{item.duration % 60:02d}")
            elif search_type == 'artist':
                print(f"{i}. {item.name}")
            elif search_type == 'album':
                print(f"{i}. {item.name}")
                print(f"   Artist: {item.artist.name}")
                print(f"   Tracks: {item.num_tracks}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_tidal_playback(query, search_type='track'):
    """Test Tidal playback via Chromecast"""
    print("=" * 60)
    print("Tidal Playback Test")
    print("=" * 60)
    print()
    
    try:
        player = TidalPlayer()
        success = player.search_and_play(query, search_type)
        
        if not success:
            print("\n❌ Playback failed")
            return False
        
        print()
        print("✅ Music is playing!")
        print("Press Ctrl+C to stop")
        print()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Stopping playback...")
            player.stop()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Tidal Integration Test")
        print("=" * 60)
        print()
        print("Usage:")
        print("  python test_tidal.py <query> [search_type] [--search-only]")
        print()
        print("Arguments:")
        print("  query         Search query")
        print("  search_type   track | artist | album (default: track)")
        print("  --search-only Only search, don't play")
        print()
        print("Examples:")
        print("  python test_tidal.py 'bohemian rhapsody' track")
        print("  python test_tidal.py 'queen' artist")
        print("  python test_tidal.py 'a night at the opera' album --search-only")
        sys.exit(1)
    
    query = sys.argv[1]
    search_type = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != '--search-only' else 'track'
    search_only = '--search-only' in sys.argv
    
    if search_only:
        success = test_tidal_search(query, search_type)
    else:
        success = test_tidal_playback(query, search_type)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
