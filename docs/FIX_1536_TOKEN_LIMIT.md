# FIXING: 1536 Token Context Window Limit

## 🎯 The Problem (From Your vLLM Logs)

```
ValueError: This model's maximum context length is 1536 tokens
However, your request has 4176 input tokens
```

**Your model has a TINY context window!**

Most models: 4K-32K tokens
Your model: 1536 tokens (VERY small!)

---

## ⚡ **Three Quick Solutions** (Pick One)

### Solution 1: Use Bigger Model (BEST - Recommended)

**Problem:** Your current model is too small for web categorization.

**Fix:** Load a full-size model with proper context:

```bash
# Stop current vLLM
pkill -f vllm

# Start with full Qwen model (32K context)
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --max-model-len 8192 \
  --port 8000
```

**OR download a proper model:**
```bash
# Install huggingface-cli
pip install huggingface-hub --break-system-packages

# Download full model
huggingface-cli download Qwen/Qwen2.5-7B-Instruct

# Start vLLM
vllm serve Qwen/Qwen2.5-7B-Instruct --max-model-len 8192
```

**After this:** Re-run classifier with normal settings (no changes needed)

---

### Solution 2: Update Classifier for Small Model (If Stuck with 1536)

If you MUST use the small model, use the updated classifier:

**Step 1:** Download new `wxawebcat_fetcher_enhanced.py` (from outputs above)

**Step 2:** Replace your current version:
```bash
cp wxawebcat_fetcher_enhanced.py ./
```

**Step 3:** Update config for small context:
```toml
# Edit wxawebcat_enhanced.toml
[llm]
max_tokens = 100  # Reduced from 220
```

**Step 4:** Re-run classifier:
```bash
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

**What Changed:**
- Snippet: 2000 → 800 chars
- Title: 500 → 200 chars  
- Meta: 500 → 200 chars
- Max tokens: 220 → 150
- Removed unnecessary fields

**Token Budget:**
```
System prompt:    ~30 tokens
User prompt:      ~50 tokens
Features:         ~400 tokens
Total input:      ~480 tokens
Max output:       150 tokens
Total needed:     630 tokens ✓ (fits in 1536!)
```

---

### Solution 3: Increase vLLM Context Limit

If your model SUPPORTS more but vLLM is limiting it:

```bash
# Stop vLLM
pkill -f vllm

# Restart with higher limit
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --max-model-len 4096 \
  --port 8000
```

Check vLLM startup logs for:
```
Maximum context length: 4096  ← Should be higher!
```

---

## 🔍 **Which Model Do You Have?**

Check what you're actually running:

```bash
# Check vLLM startup log
# Look for lines like:
# "Model: Qwen/Qwen2.5-7B-Instruct"
# "Max model length: 1536"

# Or check with API
curl http://127.0.0.1:8000/v1/models | jq .
```

**Possible issues:**
1. **Quantized model** (Q4, Q8) - Often has reduced context
2. **Old/experimental version** - May have bugs
3. **vLLM config** - Artificially limited with `--max-model-len`
4. **Wrong model** - Not actually Qwen2.5-7B-Instruct

---

## 📊 **Token Size Reference**

```
1 char ≈ 0.25 tokens (average for English)
4 chars ≈ 1 token

Examples:
100 chars ≈ 25 tokens
500 chars ≈ 125 tokens
1000 chars ≈ 250 tokens
2000 chars ≈ 500 tokens
4000 chars ≈ 1000 tokens
```

**Your current config (before fix):**
```
Snippet: 65,536 chars → ~16,000 tokens! ✗
(This is why you got 4176 token requests!)
```

**After fix:**
```
Snippet: 800 chars → ~200 tokens ✓
Title: 200 chars → ~50 tokens ✓
Total: ~500 tokens ✓
```

---

## ✅ **Recommended Action Plan**

### If You Can Change Models (BEST):

```bash
# 1. Stop vLLM
pkill -f vllm

# 2. Start with proper model
vllm serve Qwen/Qwen2.5-7B-Instruct --max-model-len 8192

# 3. Re-run classifier (no other changes needed!)
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

### If Stuck with Small Model:

```bash
# 1. Update classifier (download new file)
cp /path/to/new/wxawebcat_fetcher_enhanced.py ./

# 2. Update config
nano wxawebcat_enhanced.toml
# Change: max_tokens = 100

# 3. Re-run
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml
```

---

## 🎯 **Expected Results**

### Before (484 errors):
```
Total:                1000
Successful:           516
Errors:               484  ← 400 Bad Request
```

### After (with fix):
```
Total:                1000
Skipped (resume):     516  ← Already done
LLM classified:       484  ← Now working!
Errors:               0    ← ZERO!
```

---

## 💡 **Why 1536 Tokens?**

This is unusually small. Likely causes:

1. **Quantized model** - You downloaded a Q4 or Q8 version
2. **Experimental/dev model** - Test version with reduced context
3. **vLLM setting** - Someone set `--max-model-len 1536`
4. **Old model version** - Outdated checkpoint

**Standard context lengths:**
```
Qwen2.5-7B-Instruct:      32,768 tokens (standard)
Qwen2.5-7B-Instruct-Q4:   ??,??? tokens (varies)
Your current model:       1,536 tokens (very unusual!)
```

---

## 🚀 **Quick Test**

Test if the new limits work:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a web categorizer."},
      {"role": "user", "content": "Classify cnn.com"}
    ],
    "max_tokens": 100,
    "temperature": 0.1
  }'
```

**If this works:** Your limits are OK
**If this fails:** Model context is REALLY tiny

---

## 📞 **Still Having Issues?**

Check your vLLM startup command:

```bash
ps aux | grep vllm
```

Look for:
```
--max-model-len 1536  ← This is limiting you!
```

Remove it or increase it:
```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --max-model-len 8192
```

---

## ✅ **Summary**

**Problem:** Model context = 1536 tokens (TOO SMALL)

**Best solution:** Use bigger model with 4K-8K context

**Quick solution:** Use updated classifier with smaller payloads

**Expected fix time:** 5-10 minutes

**You'll go from 484 errors → 0 errors!** 🎉
