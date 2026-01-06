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
sudo apt install -y python3-pip python3-venv portaudio19-dev git unzip wget

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv

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
echo "   (This may take a few minutes - ~244MB download)"

if [ ! -d "vosk-model-es" ]; then
    wget -q --show-progress https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
    echo "📦 Extracting model..."
    unzip -q vosk-model-small-es-0.42.zip
    mv vosk-model-small-es-0.42 vosk-model-es
    rm vosk-model-small-es-0.42.zip
    echo "✅ Model installed"
else
    echo "✅ Spanish model already exists"
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your credentials:"
    echo "   - TIDAL_USERNAME"
    echo "   - TIDAL_PASSWORD"
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
echo "1. Edit .env file with your credentials:"
echo "   nano .env"
echo ""
echo "2. Authenticate with Tidal:"
echo "   source venv/bin/activate"
echo "   python tidal_auth.py"
echo ""
echo "3. Test Chromecast connection:"
echo "   python test_chromecast.py --discover"
echo "   python test_chromecast.py --test"
echo ""
echo "4. Update config.py with your Nest Mini name"
echo ""
echo "5. Run the application:"
echo "   python main.py"
echo ""
echo "For more information, see README.md"
echo ""
