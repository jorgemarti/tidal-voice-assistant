#!/bin/bash
# Setup script for Tidal Voice Assistant

set -e  # Exit on error

echo "======================================================================"
echo "Tidal Voice Assistant Setup"
echo "======================================================================"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update

# Install dependencies
echo "📦 Installing system dependencies..."
sudo apt install -y python3-pip python3-venv alsa-utils git unzip wget
# Optional, only for the test scripts:
# sudo apt install -y ffmpeg

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv --system-site-packages venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install Python packages
echo "📦 Installing Python packages..."
pip install -r requirements.txt

# Download Spanish Vosk model
echo "📥 Downloading Spanish speech recognition model..."
echo "   (~40MB download, ~58MB on disk)"

if [ ! -d "vosk-model-small-es-0.42" ]; then
    wget -q --show-progress https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
    echo "📦 Extracting model..."
    unzip -q vosk-model-small-es-0.42.zip
    rm vosk-model-small-es-0.42.zip
    echo "✅ Model installed"
else
    echo "✅ Spanish model already exists"
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your Gemini API key:"
    echo "   - GEMINI_API_KEY (Tidal uses OAuth, no credentials needed)"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "======================================================================"
echo "✅ Setup Complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env file and set GEMINI_API_KEY:"
echo "   nano .env"
echo ""
echo "2. Raise the USB mic gain and disable AGC (C-Media mic, card 0):"
echo "   amixer -c 0 cset numid=3 16"
echo "   amixer -c 0 cset numid=4 off"
echo "   sudo alsactl store"
echo "   arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 5 test.wav && aplay test.wav"
echo ""
echo "3. Authenticate with Tidal:"
echo "   source venv/bin/activate"
echo "   python tidal_auth.py"
echo ""
echo "4. Test Chromecast connection:"
echo "   python test_chromecast.py --discover"
echo "   python test_chromecast.py --test"
echo ""
echo "5. Update config.py with your Nest Mini name"
echo ""
echo "6. Run the application:"
echo "   python main.py"
echo ""
echo "For more information, see README.md"
echo ""
