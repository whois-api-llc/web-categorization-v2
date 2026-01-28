# Quick Reference: TOML Integration Changes

## What Changed?

The enhanced classifier now **reads configuration from wxawebcat.toml** instead of using hardcoded values.

---

## Before (Previous Version)

### Configuration
❌ **Hardcoded in Python**
```python
# Had to edit code to change settings
cfg = ClassifierConfig(
    vllm_base_url="http://127.0.0.1:8000/v1",
    model="Qwen/Qwen2.5-7B-Instruct",
    llm_concurrency=32,
    enable_content_hash_dedup=True,
    # ...
)
```

### Usage
```bash
# Only command-line args
python wxawebcat_fetcher_enhanced.py \
  --fetch-dir ./fetch \
  --out-dir ./classify
```

### To Change Settings
1. Edit Python code
2. Search for ClassifierConfig
3. Modify values
4. Save and run

---

## After (Current Version)

### Configuration
✅ **Reads from TOML file**
```toml
# Edit wxawebcat_enhanced.toml
[llm]
base_url = "http://127.0.0.1:8000/v1"
model = "Qwen/Qwen2.5-7B-Instruct"
llm_concurrency = 32

[content_hash]
enabled = true

[tld_rules]
enabled = true
```

### Usage
```bash
# Use TOML config
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# Or with command-line overrides
python wxawebcat_fetcher_enhanced.py \
  --config wxawebcat_enhanced.toml \
  --fetch-dir ./custom_fetch \
  --out-dir ./custom_output
```

### To Change Settings
1. Edit TOML file
2. Find the section
3. Update values
4. Save and run

**No code changes needed!**

---

## New TOML Sections

### 1. TLD Rules
```toml
[tld_rules]
# Enable/disable TLD-based instant classification
enabled = true
```

### 2. Content Hash
```toml
[content_hash]
# Enable/disable content hash deduplication
enabled = true
cache_file = "./logs/content_hash_cache.json"
min_content_length = 50
```

---

## Backward Compatibility

### ✅ Works with Original TOML
```bash
# Your existing wxawebcat.toml still works!
python wxawebcat_fetcher_enhanced.py --config wxawebcat.toml

# New features auto-enabled with defaults:
# - TLD rules: enabled
# - Content hash: enabled
```

### ✅ Works without TOML
```bash
# Falls back to sensible defaults
python wxawebcat_fetcher_enhanced.py \
  --fetch-dir ./fetch \
  --out-dir ./classify
```

---

## Migration Checklist

- [ ] Copy `wxawebcat_enhanced.toml` to your project
- [ ] Review new `[tld_rules]` and `[content_hash]` sections
- [ ] Adjust settings if needed (or use defaults)
- [ ] Test with: `python test_toml_config.py`
- [ ] Run classifier with: `--config wxawebcat_enhanced.toml`
- [ ] Monitor output for config confirmation

---

## Key Benefits

### Before
- ❌ Edit code to change settings
- ❌ Hard to maintain multiple environments
- ❌ Risk of breaking code

### After
- ✅ Edit TOML to change settings
- ✅ Easy dev/staging/prod configs
- ✅ No code changes needed
- ✅ Version control friendly
- ✅ Self-documenting

---

## What Stayed the Same

✅ All features work identically
✅ Output format unchanged
✅ Performance characteristics unchanged
✅ TLD rules and content hash logic unchanged
✅ Command-line arguments still work

**Only configuration method changed!**

---

## Quick Comparison Table

| Aspect | Before | After |
|--------|--------|-------|
| Config location | Python code | TOML file |
| Change settings | Edit code | Edit TOML |
| Multiple envs | Multiple .py files | Multiple .toml files |
| Version control | Risky | Safe |
| Non-programmers | Can't configure | Can configure |
| Testing changes | Full code change | Just config change |
| Rollback | Git revert code | Git revert config |

---

## Example: Changing LLM Concurrency

### Before
```python
# In wxawebcat_fetcher_enhanced.py line 25
llm_concurrency: int = 32  # Change this number
```
Then re-run the script.

### After
```toml
# In wxawebcat_enhanced.toml
[llm]
llm_concurrency = 64  # Change this number
```
Then re-run with `--config wxawebcat_enhanced.toml`

**Much safer and easier to manage!**

---

## Summary

**What you need to know:**
1. Enhanced version now reads from TOML (like the original project)
2. Use `--config wxawebcat_enhanced.toml` flag
3. All settings configurable via TOML
4. Backward compatible with existing wxawebcat.toml
5. Command-line args still work and override TOML

**Bottom line:** Same great features, better configuration management! 🎉
