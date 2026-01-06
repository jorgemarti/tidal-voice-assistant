#!/usr/bin/env python3
"""
Test Chromecast connectivity and audio casting
"""

import pychromecast
import time
import sys
import argparse
from pathlib import Path
import http.server
import socketserver
import threading
import socket
from gtts import gTTS
import tempfile
import os

def get_local_ip():
    """Get local IP address of this machine"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to external server (doesn't actually send data)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class SimpleHTTPServerThread(threading.Thread):
    """Simple HTTP server to serve audio files to Chromecast"""
    
    def __init__(self, directory, port=8000):
        super().__init__(daemon=True)
        self.directory = directory
        self.port = port
        self.httpd = None
        
    def run(self):
        """Start HTTP server"""
        os.chdir(self.directory)
        handler = http.server.SimpleHTTPRequestHandler
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        print(f"   HTTP server started on port {self.port}")
        self.httpd.serve_forever()
    
    def stop(self):
        """Stop HTTP server"""
        if self.httpd:
            self.httpd.shutdown()

def discover_chromecasts():
    """Discover all Chromecast devices on network"""
    print("🔍 Discovering Chromecast devices on network...")
    print("   (This may take up to 30 seconds)")
    print()
    
    chromecasts, browser = pychromecast.get_chromecasts()
    
    if not chromecasts:
        print("❌ No Chromecast devices found")
        print()
        print("Troubleshooting:")
        print("  1. Ensure devices are on same WiFi network")
        print("  2. Check firewall settings")
        print("  3. Restart Chromecast devices")
        return []
    
    print(f"✅ Found {len(chromecasts)} device(s):")
    print()
    
    for i, cast in enumerate(chromecasts, 1):
        print(f"{i}. {cast.name}")
        print(f"   Model: {cast.model_name}")
        print(f"   IP: {cast.cast_info.host}:{cast.cast_info.port}")
        print(f"   UUID: {cast.uuid}")
        print()
    
    return chromecasts

def test_chromecast_connection(chromecast_name=None):
    """Test connection to a specific Chromecast"""
    print("=" * 60)
    print("Chromecast Connection Test")
    print("=" * 60)
    print()
    
    if not chromecast_name:
        # Discover and let user choose
        chromecasts = discover_chromecasts()
        if not chromecasts:
            return False
        
        if len(chromecasts) == 1:
            cast = chromecasts[0]
        else:
            print("Enter device number to test:")
            try:
                choice = int(input("Device: ")) - 1
                cast = chromecasts[choice]
            except (ValueError, IndexError):
                print("❌ Invalid choice")
                return False
    else:
        print(f"Searching for: '{chromecast_name}'...")
        chromecasts, browser = pychromecast.get_listed_chromecasts(
            friendly_names=[chromecast_name]
        )
        
        if not chromecasts:
            print(f"❌ Device '{chromecast_name}' not found")
            print()
            print("Available devices:")
            discover_chromecasts()
            return False
        
        cast = chromecasts[0]
    
    print()
    print(f"Connecting to: {cast.name}")
    cast.wait()
    print(f"✅ Connected successfully!")
    print()
    
    # Get device info
    print("Device Information:")
    print(f"  Name: {cast.name}")
    print(f"  Model: {cast.model_name}")
    print(f"  Manufacturer: {cast.cast_type}")
    print(f"  IP: {cast.cast_info.host}")
    print(f"  Status: {cast.status}")
    print()
    
    return cast

def test_audio_playback(cast, audio_file=None):
    """Test audio playback on Chromecast"""
    print("=" * 60)
    print("Audio Playback Test")
    print("=" * 60)
    print()
    
    # Create temporary directory for serving files
    temp_dir = tempfile.mkdtemp()
    
    if not audio_file:
        # Generate test audio with Spanish TTS
        print("Generating test audio (Spanish)...")
        tts = gTTS(
            text="Hola, esto es una prueba del asistente de voz para Tidal. "
                 "Si puedes escuchar esto, la conexión funciona correctamente.",
            lang='es'
        )
        audio_file = os.path.join(temp_dir, 'test_audio.mp3')
        tts.save(audio_file)
        print(f"✅ Test audio created: {audio_file}")
    else:
        # Copy provided audio file to temp directory
        import shutil
        dest = os.path.join(temp_dir, Path(audio_file).name)
        shutil.copy(audio_file, dest)
        audio_file = dest
    
    print()
    
    # Start HTTP server
    server = SimpleHTTPServerThread(temp_dir, port=8765)
    server.start()
    time.sleep(1)
    
    # Get audio URL
    local_ip = get_local_ip()
    audio_url = f"http://{local_ip}:8765/{Path(audio_file).name}"
    
    print(f"Audio URL: {audio_url}")
    print()

    # Check and set volume
    current_volume = cast.status.volume_level
    print(f"Current volume: {int(current_volume * 100)}%")

    if current_volume < 0.4:
        print("Setting volume to 40% for test...")
        cast.set_volume(0.4)
        time.sleep(1)

    print()
    print("▶️  Starting playback...")

    try:
        mc = cast.media_controller
        mc.play_media(audio_url, 'audio/mpeg')
        mc.block_until_active()

        print("✅ Media controller activated!")
        print()
        print(f"Player state: {mc.status.player_state}")
        print(f"Current time: {mc.status.current_time}")
        print(f"Duration: {mc.status.duration}")
        print()
        print("You should hear:")
        print('  "Hola, esto es una prueba del asistente de voz para Tidal..."')
        print()
        print("Monitoring playback... Press Ctrl+C to stop")
        print()

        # Wait for playback and monitor status
        last_state = None
        timeout = 30  # 30 second timeout
        elapsed = 0

        while elapsed < timeout:
            current_state = mc.status.player_state

            if current_state != last_state:
                print(f"[{elapsed}s] State: {current_state} | Time: {mc.status.current_time:.1f}s / {mc.status.duration}s")
                last_state = current_state

            if current_state == 'IDLE' and elapsed > 2:
                # If IDLE after playing, we're done
                break

            time.sleep(1)
            elapsed += 1

        print()
        if elapsed >= timeout:
            print("⚠️  Playback timeout reached")
        else:
            print("✅ Playback completed")
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopping playback...")
        mc.stop()
    except Exception as e:
        print(f"\n❌ Playback error: {e}")
        return False
    finally:
        # Restore original volume
        if current_volume < 0.4:
            print(f"\nRestoring volume to {int(current_volume * 100)}%")
            cast.set_volume(current_volume)

        server.stop()
        # Clean up temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Test Chromecast connectivity and audio playback',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_chromecast.py --discover
  python test_chromecast.py --test
  python test_chromecast.py --test --name "Living Room"
  python test_chromecast.py --file my_audio.mp3 --name "Bedroom"
        """
    )
    
    parser.add_argument(
        '--discover',
        action='store_true',
        help='Discover all Chromecast devices'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test connection and audio playback'
    )
    
    parser.add_argument(
        '--name',
        type=str,
        help='Chromecast device name'
    )
    
    parser.add_argument(
        '--file',
        type=str,
        help='Audio file to play (MP3)'
    )
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if not (args.discover or args.test):
        parser.print_help()
        return
    
    if args.discover:
        discover_chromecasts()
        return
    
    if args.test:
        cast = test_chromecast_connection(args.name)
        if cast:
            print()
            test_audio_playback(cast, args.file)

if __name__ == "__main__":
    main()
