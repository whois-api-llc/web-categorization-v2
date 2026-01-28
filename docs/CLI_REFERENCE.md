# Complete CLI Command Reference

## 🔄 The Two-Stage Workflow

Your wxawebcat system has two separate stages that run independently:

### Stage 1: FETCH (Download websites)
### Stage 2: CLASSIFY (Categorize them)

---

## 📥 Stage 1: FETCH - Download Websites

### Command: wxawebcat_web_fetcher.py

**Basic Usage:**
```bash
python wxawebcat_web_fetcher.py --input domains.csv --output-dir fetch/
```

**With Configuration File:**
```bash
python wxawebcat_web_fetcher.py \
  --config wxawebcat.toml \
  --input top100.csv
```

**Limit Number of Domains:**
```bash
python wxawebcat_web_fetcher.py \
  --input top10k.csv \
  --limit 1000 \
  --output-dir fetch/
```

**Full Example:**
```bash
python wxawebcat_web_fetcher.py \
  --input top1000.csv \
  --output-dir fetch/ \
  --config wxawebcat.toml \
  --limit 500
```

### Options:
- `--input, -i` : Input CSV file with domains (required)
- `--output-dir, -o` : Output directory for JSON files (default: `./fetch`)
- `--config, -c` : TOML config file (optional, uses defaults otherwise)
- `--limit, -n` : Limit number of domains to process

### What It Does:
1. Reads domains from CSV (one per line, first column)
2. Performs DNS lookups (A, AAAA, CNAME, MX records)
3. Fetches HTTP/HTTPS content
4. Extracts title, meta description, body text
5. Saves each domain as `fetch/domain.com.json`

### Output:
```
Reading domains from top1000.csv...
Found 1000 domains to fetch
Output directory: fetch/
Fetch concurrency: 100
DNS concurrency: 50
HTTP timeout: 15.0s

Progress: 10/1000 (1.0%)
Progress: 20/1000 (2.0%)
...

======================================================================
FETCH SUMMARY
======================================================================
Total domains:        1000
Completed:            1000
Successful:           850
DNS failures:         50
HTTP failures:        80
Blocked/WAF:          20

Results saved in: fetch/
======================================================================

Next step: Run the classifier
  python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

---

## 🏷️ Stage 2: CLASSIFY - Categorize Websites

### Command: wxawebcat_fetcher_enhanced.py

**Basic Usage:**
```bash
python wxawebcat_fetcher_enhanced.py
```

**With Configuration File (Recommended):**
```bash
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

**Override Directories:**
```bash
python wxawebcat_fetcher_enhanced.py \
  --config wxawebcat_enhanced.toml \
  --fetch-dir ./fetch \
  --out-dir ./classify
```

**Full Example:**
```bash
python wxawebcat_fetcher_enhanced.py \
  --config wxawebcat_enhanced.toml \
  --fetch-dir /path/to/fetch \
  --out-dir /path/to/output
```

### Options:
- `--config` : TOML config file (optional)
- `--fetch-dir` : Input directory with JSON files (default: `./fetch`)
- `--out-dir` : Output directory for classifications (default: `./classify`)

### What It Does:
1. Reads JSON files from `fetch/`
2. Applies TLD rules (instant classification)
3. Applies content hash deduplication
4. Applies other rules (DNS failures, parked domains, etc.)
5. Calls LLM for remaining domains
6. Saves results as `classify/domain.com.class.json`

### Output:
```
Found 1000 files to classify
TLD rules: enabled (24 TLDs)
Content hash deduplication: enabled
LLM endpoint: http://127.0.0.1:8000/v1
LLM model: Qwen/Qwen2.5-7B-Instruct
LLM concurrency: 32
File concurrency: 200
Rule confidence cutoff: 0.85

=== CLASSIFICATION SUMMARY ===
Total:                1000
Skipped (resume):     0
Rule-based:           450
  ├─ TLD classified:  80
  ├─ Blocked:         50
  ├─ Unreachable:     70
  └─ Parked:          250
Hash cache hits:      300
LLM classified:       250
Errors:               0

=== CONTENT HASH CACHE STATS ===
Cache size:           350
Hits:                 300
Misses:               250
Hit rate:             54.5%
LLM calls saved:      300 (54.5%)
```

---

## 🚀 Complete Workflow Examples

### Example 1: Process Top 100 Domains

```bash
# Step 1: Fetch websites
python wxawebcat_web_fetcher.py \
  --input top100.csv \
  --output-dir fetch/

# Step 2: Classify them
python wxawebcat_fetcher_enhanced.py \
  --config wxawebcat_enhanced.toml

# Step 3: View results
ls -lh classify/
cat classify/google.com.class.json
```

### Example 2: Process Top 1000 with Config

```bash
# Step 1: Fetch (uses TOML for settings)
python wxawebcat_web_fetcher.py \
  --config wxawebcat.toml \
  --input top1000.csv

# Step 2: Classify (uses TOML for settings)
python wxawebcat_fetcher_enhanced.py \
  --config wxawebcat_enhanced.toml

# Done! Results in classify/
```

### Example 3: Custom Directories

```bash
# Step 1: Fetch to custom location
python wxawebcat_web_fetcher.py \
  --input domains.csv \
  --output-dir /data/raw_fetch

# Step 2: Classify from custom location
python wxawebcat_fetcher_enhanced.py \
  --fetch-dir /data/raw_fetch \
  --out-dir /data/classified
```

### Example 4: Incremental Processing

```bash
# Fetch batch 1
python wxawebcat_web_fetcher.py \
  --input batch1.csv \
  --output-dir fetch/

# Classify batch 1
python wxawebcat_fetcher_enhanced.py

# Fetch batch 2 (adds to existing fetch/)
python wxawebcat_web_fetcher.py \
  --input batch2.csv \
  --output-dir fetch/

# Classify batch 2 (skips already classified)
python wxawebcat_fetcher_enhanced.py
```

---

## 🧪 Testing with Sample Data

### Option 1: Use Test Data Generator

```bash
# Generate 8 sample domains (no network needed)
python generate_test_data.py

# Classify them
python wxawebcat_fetcher_enhanced.py

# View results
ls -lh classify/
```

### Option 2: Fetch Real Data (Small Sample)

```bash
# Fetch just 10 domains
python wxawebcat_web_fetcher.py \
  --input top100.csv \
  --limit 10 \
  --output-dir fetch/

# Classify them
python wxawebcat_fetcher_enhanced.py

# View results
ls -lh classify/
```

---

## 📋 Input File Formats

### Domains CSV (for fetcher)

**Simple format** (domain per line):
```csv
google.com
facebook.com
microsoft.com
```

**With header** (first column used):
```csv
domain,category
google.com,Search Engines
facebook.com,Social
```

**Comma-separated** (first column used):
```csv
google.com,Technology
facebook.com,Social Media
amazon.com,Shopping
```

---

## 📁 Directory Structure

```
your-project/
├── top100.csv                      # Input: Domains to fetch
├── wxawebcat_web_fetcher.py       # Stage 1: Fetcher
├── wxawebcat_fetcher_enhanced.py  # Stage 2: Classifier
├── wxawebcat_enhanced.toml        # Configuration
│
├── fetch/                          # Created by fetcher
│   ├── google.com.json
│   ├── facebook.com.json
│   └── ...
│
├── classify/                       # Created by classifier
│   ├── google.com.class.json
│   ├── facebook.com.class.json
│   └── ...
│
└── logs/
    ├── errors.jsonl
    └── content_hash_cache.json
```

---

## ⚙️ Configuration via TOML

Both scripts can use the same `wxawebcat_enhanced.toml` file:

```toml
[paths]
fetch_dir = "./fetch"
classify_dir = "./classify"

[fetch]
fetch_concurrency = 100
dns_concurrency = 50
http_timeout = 15

[classifier]
file_concurrency = 200
rule_confidence_cutoff = 0.85

[llm]
base_url = "http://127.0.0.1:8000/v1"
model = "Qwen/Qwen2.5-7B-Instruct"
llm_concurrency = 32

[tld_rules]
enabled = true

[content_hash]
enabled = true
cache_file = "./logs/content_hash_cache.json"
```

---

## 🔍 Checking Results

### View Fetch Results

```bash
# List fetched domains
ls -lh fetch/

# View a fetch result
cat fetch/google.com.json | jq .

# Count fetched domains
ls fetch/*.json | wc -l
```

### View Classification Results

```bash
# List classified domains
ls -lh classify/

# View a classification
cat classify/google.com.class.json | jq .

# Count classified domains
ls classify/*.class.json | wc -l

# Find TLD classifications
grep -r '"method": "rules"' classify/ | grep TLD | wc -l

# Find content hash hits
grep -r '"method": "hash_cache"' classify/ | wc -l
```

---

## 🐛 Troubleshooting

### "No JSON files found in fetch"

**Problem:** Classifier can't find input files

**Solutions:**
```bash
# Check if fetch directory exists and has files
ls -lh fetch/*.json

# Generate test data if needed
python generate_test_data.py

# Or run the fetcher first
python wxawebcat_web_fetcher.py --input top100.csv
```

### "Connection refused" (LLM)

**Problem:** vLLM server not running

**Solutions:**
```bash
# Most domains still work (rules + content hash)
# Only some domains need LLM

# Start vLLM server (in another terminal)
vllm serve Qwen/Qwen2.5-7B-Instruct

# Or disable LLM-dependent features temporarily
# (Edit config to increase rule_confidence_cutoff)
```

### "Module not found: aiodns"

**Problem:** Missing dependencies

**Solution:**
```bash
pip install httpx aiodns pycares --break-system-packages
```

---

## 📊 Performance Tips

### Faster Fetching

```bash
# Increase concurrency in TOML
[fetch]
fetch_concurrency = 200
dns_concurrency = 100

# Or use command-line
python wxawebcat_web_fetcher.py \
  --input domains.csv \
  --config fast_config.toml
```

### Faster Classification

```bash
# Increase concurrency in TOML
[llm]
llm_concurrency = 64

[classifier]
file_concurrency = 500

# Enable all optimizations
[tld_rules]
enabled = true

[content_hash]
enabled = true
```

---

## 💡 Pro Tips

1. **Run fetcher and classifier in parallel** (on different datasets)
   ```bash
   # Terminal 1
   python wxawebcat_web_fetcher.py --input batch1.csv
   
   # Terminal 2 (on previous batch)
   python wxawebcat_fetcher_enhanced.py
   ```

2. **Resume interrupted runs** (both scripts skip completed work)
   ```bash
   # Just re-run, will skip already processed domains
   python wxawebcat_web_fetcher.py --input domains.csv
   python wxawebcat_fetcher_enhanced.py
   ```

3. **Monitor progress**
   ```bash
   # Watch fetch directory grow
   watch -n 1 'ls fetch/*.json | wc -l'
   
   # Watch classify directory grow
   watch -n 1 'ls classify/*.class.json | wc -l'
   ```

---

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Fetch websites | `python wxawebcat_web_fetcher.py --input domains.csv` |
| Classify websites | `python wxawebcat_fetcher_enhanced.py` |
| Use config file | Add `--config wxawebcat_enhanced.toml` |
| Limit processing | Add `--limit 100` (fetcher only) |
| Custom directories | Add `--output-dir` / `--fetch-dir` / `--out-dir` |
| Generate test data | `python generate_test_data.py` |
| Check results | `ls -lh fetch/` or `ls -lh classify/` |

---

## 🚀 Summary

**Complete workflow in 2 commands:**

```bash
# 1. Fetch
python wxawebcat_web_fetcher.py --input top1000.csv

# 2. Classify  
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

That's it! Results will be in `classify/`
