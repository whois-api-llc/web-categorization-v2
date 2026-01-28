# Installation Guide

## Quick Install

### Option 1: Using requirements.txt (Recommended)

```bash
pip install -r requirements.txt
```

**If you need --break-system-packages:**

```bash
pip install -r requirements.txt --break-system-packages
```

### Option 2: Manual Install

```bash
# Core dependencies
pip install httpx aiodns pycares

# Or with --break-system-packages
pip install httpx aiodns pycares --break-system-packages
```

---

## Dependency Breakdown

### Required (Core)

**httpx** - HTTP client for fetching websites
- Used by: Both fetcher and classifier
- Why: Modern async HTTP library

**aiodns** - Async DNS resolver
- Used by: Web fetcher (Stage 1)
- Why: Fast concurrent DNS lookups

**pycares** - C-Ares DNS library (dependency of aiodns)
- Used by: aiodns
- Why: Low-level DNS operations

### Built-in (No Install Needed)

**tomllib** - TOML parser (Python 3.11+)
- Used by: Both scripts for config
- Fallback: `tomli` package for Python 3.10 and below

**asyncio** - Async I/O
- Built into Python 3.7+

**json, csv, re** - Standard library
- Built into Python

---

## Verification

After installation, verify everything is working:

```bash
# Check Python version
python --version

# Verify dependencies
python -c "import httpx; print('httpx:', httpx.__version__)"
python -c "import aiodns; print('aiodns: OK')"
python -c "import pycares; print('pycares: OK')"

# Or use the test script
python -c "
import httpx
import aiodns
import pycares
try:
    import tomllib
    print('tomllib: Built-in')
except ImportError:
    try:
        import tomli
        print('tomli: Installed')
    except ImportError:
        print('WARNING: No TOML parser found. Install tomli for Python < 3.11')
print('All dependencies OK!')
"
```

---

## Troubleshooting

### Error: "No module named 'aiodns'"

**Solution:**
```bash
pip install aiodns pycares --break-system-packages
```

### Error: "No module named 'httpx'"

**Solution:**
```bash
pip install httpx --break-system-packages
```

### Error: "externally-managed-environment"

**Solution 1:** Use `--break-system-packages` flag
```bash
pip install httpx aiodns pycares --break-system-packages
```

**Solution 2:** Use virtual environment (recommended for production)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Error: "No module named 'tomllib'" (Python < 3.11)

**Solution:**
```bash
pip install tomli --break-system-packages
```

Then the scripts will automatically use `tomli` instead.

### Error: Building pycares fails

**On Ubuntu/Debian:**
```bash
sudo apt-get install build-essential python3-dev
pip install pycares --break-system-packages
```

**On macOS:**
```bash
brew install python
pip install pycares
```

**On Windows:**
- Install Visual Studio Build Tools
- Or use pre-built wheels (usually automatic)

---

## Python Version Requirements

**Minimum:** Python 3.8
**Recommended:** Python 3.11+ (includes tomllib)

Check your version:
```bash
python --version
```

---

## Optional Dependencies

### For Better Performance

```bash
# Faster JSON parsing
pip install orjson --break-system-packages

# Progress bars (nice for large batches)
pip install tqdm --break-system-packages
```

### For Enhanced HTML Parsing

```bash
# Better text extraction
pip install beautifulsoup4 lxml --break-system-packages
```

---

## Virtual Environment Setup (Production)

For production deployments, use a virtual environment:

```bash
# Create virtual environment
python -m venv wxawebcat-env

# Activate it
source wxawebcat-env/bin/activate  # Linux/Mac
# or
wxawebcat-env\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run scripts
python wxawebcat_web_fetcher.py --input domains.csv
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# Deactivate when done
deactivate
```

---

## Docker Setup (Advanced)

If you want to containerize everything:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scripts
COPY *.py .
COPY *.toml .

# Run
CMD ["python", "wxawebcat_web_fetcher.py", "--help"]
```

Build and run:
```bash
docker build -t wxawebcat .
docker run -v $(pwd)/fetch:/app/fetch wxawebcat python wxawebcat_web_fetcher.py --input domains.csv
```

---

## Installation Summary

**Simplest install (one command):**
```bash
pip install httpx aiodns pycares --break-system-packages
```

**Then verify:**
```bash
python wxawebcat_web_fetcher.py --help
```

**If it works, you're done!** 🎉

---

## After Installation

Run the test data generator to verify everything works:

```bash
# Generate test data
python generate_test_data.py

# Classify it (tests the classifier)
python wxawebcat_fetcher_enhanced.py

# Fetch real domains (tests the fetcher)
python wxawebcat_web_fetcher.py --input top100.csv --limit 5
```

If all three commands work, installation is successful!
