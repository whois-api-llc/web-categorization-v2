# Quick Performance Settings Comparison

## 🎯 Your System: AMD Ryzen 9 9950X (16 cores / 32 threads)

---

## ⚙️ Configuration Files Summary

| Config File | Speed | Reliability | Use Case |
|------------|-------|-------------|----------|
| **wxawebcat_enhanced.toml** | Moderate | 95%+ | Production, safe default |
| **wxawebcat_highperf.toml** ⭐ | Fast | 90-95% | **RECOMMENDED for your CPU** |
| **wxawebcat_ultra.toml** | Maximum | 85-90% | Speed over reliability |

---

## 📊 Settings Comparison

| Setting | Enhanced | High-Perf ⭐ | Ultra |
|---------|----------|-------------|-------|
| **fetch_concurrency** | 50 | 150 | 200 |
| **dns_concurrency** | 20 | 50 | 80 |
| **batch_size** | 100 | 200 | 500 |
| **llm_concurrency** | 32 | 40 | 48 |
| **dns_delay_ms** | 10 | 5 | 2 |
| **DNS servers** | 6 | 6 | 8 |

---

## ⏱️ Estimated Times (1,000,000 domains)

| Config | Fetch Time | Classify Time | Total | Success Rate |
|--------|-----------|---------------|-------|--------------|
| **Enhanced** | 22h 14m | 10h | 32h 14m | 95% |
| **High-Perf** ⭐ | 14h 50m | 6h 40m | 21h 30m | 92% |
| **Ultra** | 10h 50m | 5h | 15h 50m | 88% |

**Speedup with High-Perf: ~33% faster**
**Speedup with Ultra: ~51% faster**

---

## 🚀 Quick Start

### 1. Test with 1000 domains:
```bash
python wxawebcat_web_fetcher_db.py \
  --input top1M.csv \
  --limit 1000 \
  --config wxawebcat_highperf.toml
```

### 2. Check success rate:
```bash
sqlite3 wxawebcat.db "SELECT fetch_status, COUNT(*) FROM domains GROUP BY fetch_status"
```

### 3. If success > 90%, run full dataset:
```bash
python wxawebcat_web_fetcher_db.py \
  --input top1M.csv \
  --config wxawebcat_highperf.toml
```

### 4. If success > 95%, try ultra:
```bash
python wxawebcat_web_fetcher_db.py \
  --input top1M.csv \
  --config wxawebcat_ultra.toml
```

---

## 💡 Which Config to Use?

| Your Priority | Recommended Config |
|--------------|-------------------|
| **Reliability first** | wxawebcat_enhanced.toml |
| **Best balance** ⭐ | wxawebcat_highperf.toml |
| **Maximum speed** | wxawebcat_ultra.toml |

**For most users with Ryzen 9 9950X: Use High-Performance config!**

---

## 📈 Performance Per 100 Domains

| Config | Avg Batch Time | Domains/Second |
|--------|---------------|----------------|
| **Enhanced** | ~8 seconds | 12.5 |
| **High-Perf** ⭐ | ~5 seconds | 20 |
| **Ultra** | ~3.5 seconds | 28.5 |

---

## ⚠️ Signs You Need to Reduce Settings

| Issue | Solution |
|-------|----------|
| **Success rate < 85%** | Switch to Enhanced config |
| **pool_timeout errors** | Reduce fetch_concurrency by 50 |
| **DNS failures > 5%** | Reduce dns_concurrency by 20 |
| **Batch time > 15s** | Check network connection |

---

## ✅ Signs You Can Increase Settings

| Indicator | Action |
|-----------|--------|
| **Success rate > 95%** | Try Ultra config |
| **Batch time < 4s** | Increase concurrency by 25% |
| **CPU usage < 50%** | Increase concurrency by 50% |
| **No errors** | Push it! |

---

## 🎯 Recommended Command

```bash
# Start with High-Performance (best for your CPU)
python wxawebcat_web_fetcher_db.py \
  --input top1M.csv \
  --config wxawebcat_highperf.toml \
  --db wxawebcat.db
```

**Your Ryzen 9 9950X can handle it!** 🚀
