# Quick Start Guide

## Installation

```bash
# Run the installation script
./install.sh
```

Or manually:
```bash
pip install -r requirements.txt
```

## Basic Usage

### 1. Initialize Database
```bash
python scripts/wxawebcat_db.py --init
```

### 2. Fetch Domains
```bash
python scripts/wxawebcat_web_fetcher_db.py \
  --input domains.csv \
  --config configs/wxawebcat_highperf.toml
```

### 3. Classify Domains
```bash
python scripts/wxawebcat_classifier_db.py \
  --db wxawebcat.db \
  --config configs/wxawebcat_highperf.toml
```

## Configuration Files

- `wxawebcat_enhanced.toml` - Balanced (safe, 95% success)
- `wxawebcat_highperf.toml` - High-performance (recommended for 16+ cores)
- `wxawebcat_ultra.toml` - Ultra-fast (32+ cores)
- `wxawebcat_extreme.toml` - Maximum speed (32+ cores, 64+ GB RAM)

## CSV Format

Your domains.csv can be:

**Single column:**
```csv
google.com
facebook.com
```

**Or rank,domain:**
```csv
1,google.com
2,facebook.com
```

Headers are automatically skipped!

## Full Documentation

See README.md for complete documentation including:
- Performance tuning
- Troubleshooting
- Advanced features
- Best practices
