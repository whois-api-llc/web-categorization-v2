# Complete Workflow Guide

## ⚠️ Issue: "No JSON files found in fetch"

This message appears because the classifier expects JSON files that don't exist yet.

**Why?** The wxawebcat system has **two separate stages**:

---

## 📋 The Two-Stage Process

### Stage 1: FETCH (Create JSON files)
Downloads websites and creates JSON files in `./fetch/`

### Stage 2: CLASSIFY (Read JSON files)  
Reads those JSON files and categorizes them

**You were running Stage 2 without Stage 1!**

---

## 🔄 Complete Workflow

### Option A: Real Data (Production)

```bash
# STAGE 1: Fetch websites (you need to implement/run this)
# This creates JSON files in ./fetch/
# Example: Use wxawebcat_fetcher.py or similar

# STAGE 2: Classify them
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

### Option B: Test Data (For Testing)

```bash
# STAGE 1: Generate test data
python generate_test_data.py

# STAGE 2: Classify test data
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

---

## 📁 Expected Directory Structure

```
your-project/
├── fetch/                          # INPUT (Stage 1 creates these)
│   ├── example.com.json           
│   ├── google.com.json
│   └── ...
├── classify/                       # OUTPUT (Stage 2 creates these)
│   ├── example.com.class.json
│   ├── google.com.class.json
│   └── ...
├── logs/
│   ├── errors.jsonl
│   └── content_hash_cache.json     # Persistent cache
├── wxawebcat_fetcher_enhanced.py   # The classifier
└── wxawebcat_enhanced.toml         # Configuration
```

---

## 📄 Fetch JSON Format

Each JSON file in `./fetch/` should look like:

```json
{
  "fqdn": "example.com",
  "dns": {
    "rcode": "NOERROR",
    "a": ["93.184.216.34"],
    "aaaa": [],
    "cname": []
  },
  "http": {
    "status": 200,
    "final_url": "https://example.com/",
    "title": "Example Domain",
    "content_type": "text/html",
    "headers": {"content-type": "text/html"},
    "body_snippet": "Example Domain. This domain is for use in examples...",
    "meta": {
      "description": "Example domain for documentation"
    },
    "blocked": false,
    "fetch_method": "aiohttp"
  }
}
```

---

## 🧪 Testing with Sample Data

I've created a test data generator that creates 8 sample domains:

### Generate Test Data

```bash
python generate_test_data.py
```

This creates:
- ✅ 3 TLD-classified domains (.gov, .edu, .xxx)
- ✅ 2 parked domains (one is duplicate for content hash test)
- ✅ 1 DNS failure
- ✅ 1 blocked site
- ✅ 1 normal site (needs LLM)

### Run Classifier on Test Data

```bash
# Option 1: With TOML config
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# Option 2: Without TOML (uses defaults)
python wxawebcat_fetcher_enhanced.py
```

### Expected Output

```
Found 8 files to classify
TLD rules: enabled (24 TLDs)
Content hash deduplication: enabled
LLM endpoint: http://127.0.0.1:8000/v1
...

=== CLASSIFICATION SUMMARY ===
Total:                8
Skipped (resume):     0
Rule-based:           6
  ├─ TLD classified:  3  ← cdc.gov, mit.edu, example.xxx
  ├─ Blocked:         1  ← blocked-example.com
  ├─ Unreachable:     1  ← nonexistent-domain-*.com
  └─ Parked:          1  ← parked-example-1.com
Hash cache hits:      1  ← parked-example-2.net (duplicate!)
LLM classified:       1  ← example-shop.com
Errors:               0

=== CONTENT HASH CACHE STATS ===
Cache size:           1
Hits:                 1
Misses:               1
Hit rate:             50.0%
LLM calls saved:      1 (50.0%)
```

---

## 🚀 Production Usage

### Step 1: Create Fetch Data

You need to run your fetcher to create the JSON files. This could be:

1. **Your existing fetcher script**
   ```bash
   # Example (adapt to your setup)
   python your_fetcher.py --input domains.csv --output fetch/
   ```

2. **Manual creation** (for testing specific domains)
   ```python
   # Create a JSON file manually
   import json
   
   data = {
       "fqdn": "example.com",
       "dns": {...},
       "http": {...}
   }
   
   with open("fetch/example.com.json", "w") as f:
       json.dump(data, f, indent=2)
   ```

### Step 2: Run Classifier

```bash
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

### Step 3: Check Results

```bash
# View classified domains
ls -lh classify/

# View a classification result
cat classify/example.com.class.json
```

Example output:
```json
{
  "fqdn": "example.com",
  "decision": {
    "method": "llm",
    "category": "Technology",
    "confidence": 0.85,
    "reason": "Educational technology platform"
  },
  "signals": {
    "http_status": 200,
    "title": "Example Domain",
    ...
  }
}
```

---

## 🔍 Troubleshooting

### Problem: "No JSON files found in fetch"

**Solutions:**
1. ✅ Run `generate_test_data.py` for testing
2. ✅ Run your fetcher to create real data
3. ✅ Check if `./fetch/` directory exists
4. ✅ Verify JSON files are in `./fetch/` (not a subdirectory)

### Problem: "vLLM connection refused"

The test data generator creates data that will work even without vLLM!

Most domains (7 out of 8) will be classified by rules:
- TLD rules: 3 domains
- Content rules: 3 domains  
- Content hash: 1 domain

Only 1 domain needs LLM (example-shop.com)

**Solutions:**
1. ✅ Test without LLM - 87.5% still work!
2. ✅ Start vLLM server
3. ✅ Update config to point to different LLM endpoint

### Problem: Files exist but still not found

```bash
# Check fetch directory
ls -lh fetch/

# Verify JSON extension
ls fetch/*.json

# Check current directory
pwd  # Should be in project root
```

---

## 📊 Workflow Comparison

### Before (Original System)
```
fetch/ (empty) → ❌ Can't classify

Solution: Run fetcher first
```

### After (With Test Data)
```
generate_test_data.py → fetch/ (8 files) → ✅ Can classify
```

### Production
```
your_fetcher.py → fetch/ (many files) → ✅ Can classify
```

---

## 🎯 Quick Start Summary

**For Testing:**
```bash
# 1. Generate test data
python generate_test_data.py

# 2. Run classifier
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# 3. Check results
ls -lh classify/
```

**For Production:**
```bash
# 1. Run your fetcher (creates fetch/*.json)
python your_fetcher_script.py --input domains.csv

# 2. Run classifier
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# 3. Check results
ls -lh classify/
```

---

## 💡 Key Takeaways

1. **Two stages**: Fetch first, then classify
2. **Test data generator**: Use `generate_test_data.py` for testing
3. **Production**: Run your fetcher to create JSON files
4. **Input directory**: `./fetch/` must contain `*.json` files
5. **Output directory**: `./classify/` will contain results

The classifier works perfectly - it just needs input files to process! 🎉
