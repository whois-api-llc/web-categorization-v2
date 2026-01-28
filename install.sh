#!/bin/bash
# wxawebcat installation script

echo "=== wxawebcat Installation ==="
echo ""

# Check Python version
python3 --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Error: Python 3 not found"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "✅ Python 3 found"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "⚠️  Warning: Some dependencies may have failed to install"
fi

# Make scripts executable
chmod +x scripts/*.py scripts/*.sh 2>/dev/null

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Quick Start:"
echo "  1. Initialize database:"
echo "     python scripts/wxawebcat_db.py --init"
echo ""
echo "  2. Fetch domains:"
echo "     python scripts/wxawebcat_web_fetcher_db.py \\"
echo "       --input domains.csv \\"
echo "       --config configs/wxawebcat_highperf.toml"
echo ""
echo "  3. Classify domains:"
echo "     python scripts/wxawebcat_classifier_db.py \\"
echo "       --db wxawebcat.db \\"
echo "       --config configs/wxawebcat_highperf.toml"
echo ""
echo "See README.md for full documentation"
