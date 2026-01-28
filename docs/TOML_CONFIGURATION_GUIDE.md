# TOML Configuration Guide

## Overview

The enhanced wxawebcat classifier now fully integrates with TOML configuration files, making it easy to customize all settings without modifying code.

## Quick Start

### Option 1: Use TOML Config (Recommended)

```bash
# Use the enhanced TOML configuration
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# Or specify custom input/output directories
python wxawebcat_fetcher_enhanced.py \
  --config wxawebcat_enhanced.toml \
  --fetch-dir /path/to/fetch \
  --out-dir /path/to/output
```

### Option 2: Command-Line Only

```bash
# Run without config file (uses defaults)
python wxawebcat_fetcher_enhanced.py \
  --fetch-dir ./fetch \
  --out-dir ./classify
```

### Option 3: Backward Compatible (Original TOML)

```bash
# Works with your existing wxawebcat.toml
# New features enabled by default with sensible defaults
python wxawebcat_fetcher_enhanced.py --config wxawebcat.toml
```

---

## Configuration File Structure

### New Sections Added

#### 1. TLD Rules Configuration

```toml
[tld_rules]

# Enable/disable TLD-based instant classification
enabled = true

# Currently supported TLDs:
# - Government: .gov, .mil, .gov.uk, .gov.au, .gov.ca
# - Education: .edu, .ac.uk, .edu.au, .edu.cn
# - Adult: .xxx, .adult, .porn, .sex
# - Finance: .bank, .insurance
# - Technology: .crypto, .nft, .blockchain
# - Other: .museum, .church, .test, .localhost, etc.
```

**When to disable:**
- You're only crawling .com domains
- You want LLM to make all decisions
- You have custom TLD requirements

#### 2. Content Hash Configuration

```toml
[content_hash]

# Enable/disable content hash deduplication
enabled = true

# Where to store the persistent cache
cache_file = "./logs/content_hash_cache.json"

# Minimum content length to hash (avoid false positives)
min_content_length = 50
```

**When to disable:**
- Small one-time crawls (<1000 domains)
- Highly unique content (e.g., news sites only)
- Testing/debugging LLM prompts

---

## Configuration Hierarchy

Settings are applied in this order (later overrides earlier):

1. **Code defaults** (in ClassifierConfig dataclass)
2. **TOML file** (if --config specified)
3. **Command-line arguments** (--fetch-dir, --out-dir)

### Example:

```toml
# wxawebcat_enhanced.toml
[paths]
fetch_dir = "./fetch"
classify_dir = "./classify"
```

```bash
# Command overrides TOML
python wxawebcat_fetcher_enhanced.py \
  --config wxawebcat_enhanced.toml \
  --fetch-dir /mnt/data/fetch \
  --out-dir /mnt/data/output

# Result: Uses /mnt/data/fetch and /mnt/data/output
```

---

## Complete Configuration Reference

### All Settings That Affect the Classifier

```toml
[paths]
fetch_dir = "./fetch"           # Input directory (override with --fetch-dir)
classify_dir = "./classify"     # Output directory (override with --out-dir)
log_dir = "./logs"              # Log directory

[classifier]
resume_enabled = true           # Skip already-classified domains
rule_confidence_cutoff = 0.85   # Confidence threshold for skipping LLM
file_concurrency = 200          # Concurrent file I/O operations

[llm]
base_url = "http://127.0.0.1:8000/v1"  # vLLM endpoint
model = "Qwen/Qwen2.5-7B-Instruct"     # Model name
llm_concurrency = 32                    # Concurrent LLM requests
request_timeout = 60                    # Request timeout (seconds)
temperature = 0.1                       # Sampling temperature
max_tokens = 220                        # Max output tokens

[tld_rules]
enabled = true                  # Enable TLD classification

[content_hash]
enabled = true                  # Enable content hash deduplication
cache_file = "./logs/content_hash_cache.json"  # Cache location
min_content_length = 50         # Minimum chars to hash

[logging]
error_log = "./logs/errors.jsonl"  # Error log location
enable_summary = true              # Print summary at end
log_level = "INFO"                 # DEBUG | INFO | WARN | ERROR
```

---

## Usage Examples

### Example 1: Disable All Enhancements

If you want to test LLM-only classification:

```toml
[tld_rules]
enabled = false

[content_hash]
enabled = false
```

### Example 2: Aggressive Caching

For maximum LLM savings:

```toml
[content_hash]
enabled = true
min_content_length = 20  # Hash shorter content (more aggressive)
```

### Example 3: Development/Testing

```toml
[llm]
llm_concurrency = 1     # Sequential processing
request_timeout = 120   # Longer timeout

[classifier]
file_concurrency = 10   # Less aggressive I/O

[logging]
log_level = "DEBUG"     # Verbose logging
```

### Example 4: High-Performance Production

```toml
[llm]
llm_concurrency = 64    # High parallelism
request_timeout = 30    # Short timeout

[classifier]
file_concurrency = 500  # Aggressive I/O

[tld_rules]
enabled = true          # Max optimization

[content_hash]
enabled = true
min_content_length = 50
```

---

## Monitoring & Debugging

### Check What Configuration Is Being Used

The classifier prints configuration on startup:

```
Found 1000 files to classify
TLD rules: enabled (24 TLDs)
Content hash deduplication: enabled
LLM endpoint: http://127.0.0.1:8000/v1
LLM model: Qwen/Qwen2.5-7B-Instruct
LLM concurrency: 32
File concurrency: 200
Rule confidence cutoff: 0.85
```

### Test Configuration Parsing

```bash
python test_toml_config.py
```

This will verify:
- TOML file is valid
- All sections parse correctly
- Command-line overrides work
- Defaults work for missing sections

---

## Migration Guide

### From Original wxawebcat.toml

**Option A: Use as-is (Recommended)**
```bash
# Your existing TOML works fine!
# New features auto-enabled with defaults
python wxawebcat_fetcher_enhanced.py --config wxawebcat.toml
```

**Option B: Add new sections**
```bash
# Copy wxawebcat.toml to wxawebcat_enhanced.toml
cp wxawebcat.toml wxawebcat_enhanced.toml

# Add these sections at the end:
```

```toml
[tld_rules]
enabled = true

[content_hash]
enabled = true
cache_file = "./logs/content_hash_cache.json"
min_content_length = 50
```

### From Hardcoded Config

If you were using the previous enhanced version with hardcoded config:

**Before:**
```python
# Had to edit code
cfg = ClassifierConfig(
    enable_content_hash_dedup=False,
    # ...
)
```

**Now:**
```toml
# Edit TOML instead
[content_hash]
enabled = false
```

---

## Best Practices

### 1. Version Control Your Config

```bash
# Keep configs in git
git add wxawebcat_enhanced.toml
git commit -m "Update classifier config for production"
```

### 2. Environment-Specific Configs

```bash
# Development
wxawebcat_dev.toml

# Staging
wxawebcat_staging.toml

# Production
wxawebcat_prod.toml

# Use:
python wxawebcat_fetcher_enhanced.py --config wxawebcat_prod.toml
```

### 3. Document Your Changes

```toml
# Production config - Updated 2025-01-27
# Increased concurrency for new server
[llm]
llm_concurrency = 64  # Was 32, increased due to better hardware
```

### 4. Test Config Changes

```bash
# Test with small dataset first
python wxawebcat_fetcher_enhanced.py \
  --config new_config.toml \
  --fetch-dir ./test_fetch \
  --out-dir ./test_output
```

---

## Troubleshooting

### "No such file: wxawebcat.toml"

**Solution:** Specify full path
```bash
python wxawebcat_fetcher_enhanced.py --config /path/to/wxawebcat.toml
```

### "Invalid TOML syntax"

**Solution:** Validate TOML
```bash
# Check syntax
python -c "import tomllib; tomllib.load(open('wxawebcat.toml', 'rb'))"
```

### "Config values not taking effect"

**Check:**
1. Are you using --config flag?
2. Is the section name correct?
3. Are command-line args overriding TOML?

**Debug:**
```bash
# See what config is loaded
python wxawebcat_fetcher_enhanced.py --config wxawebcat.toml
# Check startup output for confirmation
```

### "Features disabled but still running"

**Check:**
```toml
# Make sure these are lowercase "true/false"
[tld_rules]
enabled = false  # ✓ Correct

[tld_rules]
enabled = False  # ✗ May not work (capital F)
```

---

## Summary

✅ **Full TOML integration** - No more hardcoded configs
✅ **Backward compatible** - Works with existing wxawebcat.toml
✅ **Command-line overrides** - Easy testing and automation
✅ **Sensible defaults** - Works out of the box
✅ **Environment flexibility** - Dev, staging, prod configs

The enhanced classifier is now a drop-in replacement with better configurability!
