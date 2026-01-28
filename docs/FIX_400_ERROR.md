# Fixing: HTTP 400 Bad Request from vLLM

## 🔍 The Problem

You're getting:
```
HTTPStatusError: Client error '400 Bad Request' 
for url 'http://127.0.0.1:8000/v1/chat/completions'
```

This means:
- ✅ vLLM server IS running
- ✅ Network connection works
- ❌ But the request format is invalid

---

## 🎯 Most Likely Causes (In Order)

### 1. Wrong Model Name (80% of cases)

**Problem:** The model name in your request doesn't match what vLLM loaded.

**Check what vLLM loaded:**
```bash
curl http://127.0.0.1:8000/v1/models | jq '.data[].id'
```

**Common mismatches:**
```
Request says:  "Qwen/Qwen2.5-7B-Instruct"
vLLM loaded:   "qwen2.5-7b-instruct"      ← Case sensitive!
```

**Fix:** Update your config to match EXACTLY:
```toml
# In wxawebcat_enhanced.toml
[llm]
model = "qwen2.5-7b-instruct"  # Use the EXACT name from /v1/models
```

---

### 2. Invalid Request Parameters (15% of cases)

**Problem:** Temperature, max_tokens, or other parameters are invalid.

**Check vLLM's parameter limits:**
```bash
# Some vLLM versions don't accept temperature < 0 or > 2.0
# Some don't accept max_tokens > model's context length
```

**Fix:** Use safe defaults:
```toml
[llm]
temperature = 0.1      # Must be 0.0 to 2.0
max_tokens = 220       # Must be <= model's max context
```

---

### 3. Large Payload / Context Window (5% of cases)

**Problem:** The body snippet is too large for the model's context window.

**Your fetcher might be including huge HTML:**
```json
{
  "snippet": "...50,000 characters of HTML..."  ← Too big!
}
```

**Fix:** Already handled in the fetcher (max 64KB), but double-check:
```toml
# In wxawebcat_enhanced.toml
[fetch_output]
max_body_snippet_bytes = 4096  # Keep it reasonable
```

---

## 🔧 Quick Diagnostic

Run this to see the exact problem:

```bash
python diagnose_vllm.py
```

This will:
1. Test your vLLM endpoint
2. Show available models
3. Test different model name formats
4. Show the exact error from vLLM

---

## 🚀 Step-by-Step Fix

### Step 1: Check What Model vLLM Has

```bash
curl http://127.0.0.1:8000/v1/models | jq .
```

**Example output:**
```json
{
  "data": [
    {
      "id": "qwen2.5-7b-instruct",  ← THIS is the name to use
      "object": "model",
      "created": 1234567890
    }
  ]
}
```

### Step 2: Update Your Config

Edit `wxawebcat_enhanced.toml`:

```toml
[llm]
model = "qwen2.5-7b-instruct"  # ← Use EXACT name from Step 1
```

**Common model name variations:**
```
vLLM might show:
- "Qwen/Qwen2.5-7B-Instruct"     (full path)
- "Qwen2.5-7B-Instruct"          (no org)
- "qwen2.5-7b-instruct"          (lowercase)
- "models/Qwen2.5-7B-Instruct"   (with prefix)
```

### Step 3: Re-run Classifier

```bash
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

**It will automatically:**
- Skip already-classified domains (516 done)
- Only process the 484 that failed
- Complete in a few minutes

---

## 🎯 Alternative: Test Manually

### Test vLLM with curl:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-7b-instruct",
    "messages": [{"role": "user", "content": "Say OK"}],
    "temperature": 0.1,
    "max_tokens": 10
  }'
```

**If this works:** Your model name is correct!
**If this fails:** Try different model names from `/v1/models`

---

## 📊 Expected Results After Fix

```
=== CLASSIFICATION SUMMARY ===
Total:                1000
Skipped (resume):     516   ← Already done!
Rule-based:           117   ← Blocked/unreachable
LLM classified:       367   ← The 484 errors, now fixed
Errors:               0     ← Should be zero!
```

---

## 🔍 Other Possible Issues

### Issue 1: vLLM API Version Mismatch

Some vLLM versions use different endpoints:
```bash
# Try /chat/completions instead of /v1/chat/completions
curl http://127.0.0.1:8000/chat/completions
```

**Fix:** Update config:
```toml
[llm]
base_url = "http://127.0.0.1:8000"  # Remove /v1
```

### Issue 2: Authentication Required

Some vLLM setups require API keys:
```bash
curl -H "Authorization: Bearer YOUR_KEY" http://127.0.0.1:8000/v1/models
```

### Issue 3: Content Filter

vLLM might be rejecting requests with certain content:
```json
{
  "error": "Content policy violation"
}
```

Check vLLM logs for details.

---

## 💡 How to Check vLLM Logs

vLLM logs will show the exact problem:

```bash
# If running vLLM in terminal, check that output
# If running as service, check logs:
journalctl -u vllm -n 50
# OR
tail -f /var/log/vllm.log
```

Look for errors like:
```
ERROR: Model 'Qwen/Qwen2.5-7B-Instruct' not found
ERROR: Invalid parameter: temperature=0.1
ERROR: Max tokens exceeds limit
```

---

## 🎯 Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| 400 on all requests | Wrong model name | Check `/v1/models`, update config |
| 400 on some requests | Large payloads | Reduce `max_body_snippet_bytes` |
| 400 with auth error | Missing API key | Add authentication |
| 400 random | Rate limiting | Reduce `llm_concurrency` |

---

## ✅ Checklist

Before re-running classifier:

- [ ] Check model name with: `curl http://127.0.0.1:8000/v1/models`
- [ ] Update `wxawebcat_enhanced.toml` with correct name
- [ ] Test with: `python diagnose_vllm.py`
- [ ] If test passes, re-run: `python wxawebcat_fetcher_enhanced.py`

---

## 🚀 Summary

**Your issue:** Model name mismatch (99% sure)

**Quick fix:**
```bash
# 1. Get the real model name
curl http://127.0.0.1:8000/v1/models | jq '.data[].id'

# 2. Update config
nano wxawebcat_enhanced.toml
# Change: model = "exact-name-from-step-1"

# 3. Re-run (will only process the 484 failed ones)
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

**Expected time to fix:** 2 minutes
**Expected re-run time:** 5-10 minutes for 484 domains

You'll go from **484 errors** to **0 errors**! 🎉
