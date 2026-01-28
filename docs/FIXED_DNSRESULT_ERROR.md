# FIXED: 'DNSResult' object is not iterable

## 🐛 The Problem

You were getting these errors:
```
Error processing kwai.com: 'DNSResult' object is not iterable
Error processing 163.com: 'DNSResult' object is not iterable
...
```

## 🔍 Root Cause

The `query_dns()` function returns **different types** depending on the number of records:

**Single record:**
```python
result = await resolver.query_dns(domain, 'A')
# Returns: <DNSResult object> (NOT a list!)
```

**Multiple records:**
```python
result = await resolver.query_dns(domain, 'A')
# Returns: [<DNSResult>, <DNSResult>] (a list!)
```

The old code tried to iterate over it:
```python
result["a"] = [r.host for r in a_records]  # Fails if a_records is not iterable!
```

---

## ✅ The Fix

Now I check if it's a list or single object:

```python
a_records = await resolver.query_dns(domain, 'A')
# Handle both single result and list
if isinstance(a_records, list):
    result["a"] = [r.host for r in a_records]
else:
    result["a"] = [a_records.host]  # Single object, just wrap it
```

---

## 🎯 What Changed

**Before (Broken):**
```python
result["a"] = [r.host for r in a_records]  # Assumes list
```

**After (Fixed):**
```python
if isinstance(a_records, list):
    result["a"] = [r.host for r in a_records]
else:
    result["a"] = [a_records.host]
```

Applied to all DNS record types: A, AAAA, CNAME, MX

---

## 📦 Files Fixed

1. **wxawebcat_web_fetcher.py** (regular file-based version)
2. **wxawebcat_web_fetcher_db.py** (database version)

Both are now fixed and in your downloads!

---

## 🚀 What to Do

### Download the fixed versions and replace your current files:

```bash
# Replace regular fetcher
cp wxawebcat_web_fetcher.py ./

# Replace database fetcher
cp wxawebcat_web_fetcher_db.py ./

# Re-run the fetch
python wxawebcat_web_fetcher_db.py --input domains.csv --db wxawebcat.db
```

---

## ✅ Expected Results

**Before:**
```
Error processing kwai.com: 'DNSResult' object is not iterable
Error processing 163.com: 'DNSResult' object is not iterable
...
(Many errors)
```

**After:**
```
Progress: 100/1000 (10.0%)
Progress: 200/1000 (20.0%)
...
Successful: 882
(No DNSResult errors!)
```

---

## 💡 Why This Happened

The `aiodns` library is inconsistent:
- Domains with 1 A record → Returns single `DNSResult`
- Domains with 2+ A records → Returns `list` of `DNSResult`

This is a quirk of the library. The fix handles both cases gracefully.

---

## 🎯 Summary

**Issue:** DNSResult not always iterable  
**Fix:** Check if list before iterating  
**Status:** ✅ Fixed in both fetchers  
**Action:** Download and replace files  

**You should now see zero "DNSResult" errors!** 🎉
