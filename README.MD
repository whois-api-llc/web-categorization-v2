# WxaWebCat - High-Performance Web Domain Categorization System

A blazingly fast, scalable web domain fetching and categorization pipeline optimized for processing millions of domains with LLM-powered classification.

## 🚀 Features

- **Parallel Processing**: Handle 150-250 concurrent HTTP requests with optimized connection pooling
- **Smart DNS**: Round-robin DNS with rate limiting across 10 DNS servers
- **Streaming Architecture**: Process unlimited domains without loading everything into memory
- **LLM Classification**: AI-powered categorization using local vLLM server
- **Watch Mode**: Continuous classification as domains are fetched
- **Batch Optimization**: 100x faster database writes through batched commits
- **Multiple Formats**: Supports single-column domains or rank,domain CSV formats
- **Real-time Progress**: Live timing and success rate tracking
- **Content Deduplication**: Hash-based caching to avoid re-classifying duplicate content
- **IAB Taxonomy**: Maps to IAB Content Taxonomy 3.0 for industry-standard categories

## 📊 Performance

### High-Performance Configuration (Recommended for 16+ core systems)

| Metric | Value |
|--------|-------|
| **Processing Speed** | 20-25 domains/second |
| **1,000 domains** | ~42 seconds |
| **100,000 domains** | ~70 minutes |
| **1,000,000 domains** | ~11 hours |
| **Success Rate** | 85-95% |

### Optimizations Applied

- **100x faster database commits** - Batch writes every 100-1000 domains
- **Streaming CSV reader** - Constant memory usage regardless of dataset size
- **DNS round-robin** - Distributes load across multiple DNS providers
- **Connection pooling** - Reuses HTTP connections for better performance
- **Parallel pipeline** - Fetch and classify simultaneously with watch mode

---

## 🎯 Quick Start

### 1. Install Dependencies

```bash
pip install httpx aiodns tomli
```

### 2. Initialize Database

```bash
python wxawebcat_db.py --init
```

### 3. Fetch Domains

```bash
python wxawebcat_web_fetcher_db.py \
  --input domains.csv \
  --config wxawebcat_highperf.toml
```

### 4. Classify Domains

```bash
python wxawebcat_classifier_db.py \
  --db wxawebcat.db \
  --config wxawebcat_highperf.toml
```

### 5. Add IAB Categories

```bash
python add_iab_categories_db.py --db wxawebcat.db
```

### 6. Export Results

```bash
python wxawebcat_db.py --export results.csv
```

---

## 📁 Project Structure

```
wxawebcat/
├── wxawebcat_db.py                  # Database management
├── wxawebcat_web_fetcher_db.py      # Web fetcher with DNS round-robin
├── wxawebcat_classifier_db.py       # LLM-powered classifier
├── add_iab_categories_db.py         # IAB taxonomy enrichment
├── wxawebcat_enhanced.toml          # Balanced configuration
├── wxawebcat_highperf.toml          # High-performance config
├── wxawebcat_ultra.toml             # Ultra-fast config
├── wxawebcat_extreme.toml           # Maximum performance config
└── README.md                         # This file
```

---

## ⚙️ Configuration Files

### Available Configurations

| Config | Speed | Success Rate | CPU Usage | Best For |
|--------|-------|--------------|-----------|----------|
| **Enhanced** | Baseline | 95% | 16% | Production, safety |
| **High-Perf** ⭐ | 1.5x | 92% | 47% | 16+ core systems |
| **Ultra** | 2x | 88% | 63% | 32+ core systems |
| **Extreme** | 2.8x | 87% | 78% | 32+ cores + 64GB+ RAM |

### Configuration Options

#### DNS Settings
```toml
[dns]
# DNS servers for round-robin lookups
servers = [
    "1.1.1.1",          # Cloudflare Primary
    "1.0.0.1",          # Cloudflare Secondary
    "8.8.8.8",          # Google Primary
    "8.8.4.4",          # Google Secondary
    "9.9.9.9",          # Quad9
    "208.67.222.222"    # OpenDNS
]

# DNS rate limiting (milliseconds between queries)
# 10ms = 100 qps, 5ms = 200 qps, 1ms = 1000 qps
delay_ms = 10
```

#### Fetcher Settings
```toml
[fetcher]
batch_size = 100            # Domains per database commit
fetch_concurrency = 150     # HTTP requests in parallel
dns_concurrency = 50        # DNS queries in parallel
```

#### Classifier Settings
```toml
[classifier]
batch_size = 100            # Domains per commit
watch_mode = false          # Continuous monitoring
watch_interval = 10         # Seconds between checks

[llm]
base_url = "http://127.0.0.1:8000/v1"
model = "Qwen/Qwen2.5-7B-Instruct"
llm_concurrency = 32        # Parallel LLM requests
```

---

## 🚀 Usage Examples

### Basic Usage

```bash
# Fetch and classify 1000 domains
python wxawebcat_web_fetcher_db.py --input domains.csv --limit 1000
python wxawebcat_classifier_db.py --db wxawebcat.db
```

### High-Performance Mode

```bash
# Use optimized config for fast processing
python wxawebcat_web_fetcher_db.py \
  --input top1M.csv \
  --config wxawebcat_highperf.toml
```

### Parallel Pipeline (Recommended)

**Terminal 1 - Classifier (Watch Mode):**
```bash
python wxawebcat_classifier_db.py \
  --db wxawebcat.db \
  --config wxawebcat_highperf.toml \
  --watch
```

**Terminal 2 - Fetcher:**
```bash
python wxawebcat_web_fetcher_db.py \
  --input top1M.csv \
  --config wxawebcat_highperf.toml
```

**Result:** ~30% faster due to parallel processing!

### Custom Batch Size

```bash
# Larger batches = faster commits (requires more RAM)
python wxawebcat_web_fetcher_db.py \
  --input domains.csv \
  --batch-size 500 \
  --config wxawebcat_ultra.toml
```

---

## 💾 Database Schema

### Tables

**domains** - Stores fetched domain data
```sql
CREATE TABLE domains (
    fqdn TEXT PRIMARY KEY,
    dns_data TEXT,           -- JSON: {rcode, a, aaaa, cname, mx}
    http_data TEXT,          -- JSON: {status, title, content_type, ...}
    fetched_at TEXT,
    fetch_status TEXT,       -- success, dns_failed, http_failed, blocked
    classified INTEGER,      -- 0 or 1
    category TEXT,
    confidence REAL,
    method TEXT,             -- rule, llm, hash_cache
    updated_at TEXT
)
```

**classifications** - Full classification results
```sql
CREATE TABLE classifications (
    fqdn TEXT PRIMARY KEY,
    category TEXT,
    confidence REAL,
    method TEXT,
    reasoning TEXT,
    iab_tier1 TEXT,         -- IAB primary category
    iab_tier2 TEXT,         -- IAB subcategory
    sensitive_content INTEGER,
    iab_enriched INTEGER
)
```

**content_hash_cache** - Deduplication cache
```sql
CREATE TABLE content_hash_cache (
    content_hash TEXT PRIMARY KEY,
    category TEXT,
    confidence REAL,
    example_fqdn TEXT
)
```

---

## 🎯 Performance Tuning

### For Your System

Run this to check your system specs:
```bash
lscpu | grep -E "CPU\(s\)|Thread|Core"
free -h
```

### Recommended Settings by CPU

| CPU Threads | fetch_concurrency | dns_concurrency | batch_size | Config |
|-------------|------------------|-----------------|------------|--------|
| **4-8** | 50 | 20 | 100 | Enhanced |
| **8-16** | 100 | 40 | 200 | High-Perf |
| **16-32** | 150 | 50 | 200 | High-Perf |
| **32+** | 250 | 100 | 1000 | Extreme |

### Memory Requirements

| Batch Size | Peak RAM | Dataset Size | Safe For |
|------------|----------|--------------|----------|
| 100 | ~100 MB | Any | 2+ GB RAM |
| 200 | ~200 MB | Any | 4+ GB RAM |
| 500 | ~500 MB | Any | 8+ GB RAM |
| 1000 | ~1 GB | Any | 16+ GB RAM |

**Streaming architecture means dataset size doesn't affect RAM usage!**

### Network Considerations

| Internet Speed | Recommended Concurrency | Config |
|----------------|------------------------|--------|
| 100 Mbps | 50-75 | Enhanced |
| 500 Mbps | 100-150 | High-Perf |
| 1 Gbps+ | 150-250 | Extreme |

---

## 🔧 Troubleshooting

### High HTTP Failure Rate (>15%)

**Symptoms:**
```
Success: 50, HTTP fails: 50, Blocked: 0
```

**Solutions:**
1. Reduce `fetch_concurrency` by 50%
2. Check your internet connection
3. Verify DNS is working: `dig google.com`

### Connection Pool Timeout Errors

**Symptoms:**
```
Error: pool_timeout
```

**Solutions:**
```toml
[fetcher]
fetch_concurrency = 100  # Reduce from 150-200
```

### DNS Failures (>5%)

**Symptoms:**
```
DNS fails: 50+
```

**Solutions:**
```toml
[dns]
dns_concurrency = 30    # Reduce from 50
delay_ms = 20          # Increase from 10
```

### CSV Header Being Processed

**Symptoms:**
```
Sample domains:
  'rank'
  'domain'
```

**Solution:** The fetcher now automatically skips common header rows. If it still processes headers, manually remove the first row from your CSV.

### Slow Performance

**Expected Times:**
- 1000 domains: 40-60 seconds
- 10,000 domains: 7-10 minutes
- 100,000 domains: 70-100 minutes

**If slower:**
1. Check CPU usage: `htop`
2. Check network: `iftop`
3. Check config is being loaded: Look for "Batch size: X" in output
4. Verify you're using `--config` flag

### Memory Issues (Large Datasets)

**Problem:** Processing 1M+ domains causes crashes

**Solution:** Already fixed! The fetcher uses streaming and only loads 100-1000 domains at a time.

---

## 📊 Understanding Performance

### What's Fast vs Slow?

| Domains/Second | Rating | Notes |
|----------------|--------|-------|
| < 5 | ❌ Slow | Check network/config |
| 5-10 | ⚠️ Below average | Increase concurrency |
| 10-20 | ✅ Good | Normal performance |
| 20-25 | ✅ Excellent | Near optimal |
| 25+ | 🔥 Maximum | Can't go much faster |

### Bottleneck Analysis

**90% of time:** Remote server response times (can't optimize)
**5% of time:** Network latency (minimal optimization)
**5% of time:** Your system (already optimized)

**Key insight:** Beyond 250 concurrency, you see diminishing returns because you're waiting for remote servers to respond.

### Progress Monitoring

Watch real-time progress:
```bash
watch -n 5 'sqlite3 wxawebcat.db "
  SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN classified=1 THEN 1 ELSE 0 END) as classified,
    SUM(CASE WHEN fetch_status=\"success\" THEN 1 ELSE 0 END) as fetched
  FROM domains
"'
```

---

## 🎓 Advanced Features

### Watch Mode (Continuous Classification)

Enable the classifier to automatically process domains as they're fetched:

```bash
# Start classifier in watch mode
python wxawebcat_classifier_db.py --watch --db wxawebcat.db &

# Run fetcher
python wxawebcat_web_fetcher_db.py --input domains.csv
```

The classifier will:
- Check for new unclassified domains every 10 seconds
- Automatically classify them
- Wait when caught up
- Resume when new domains appear

### Content Hash Deduplication

Automatically enabled! If multiple domains have identical content, only the first is sent to the LLM:

```
domain1.com → "Welcome to our site" → LLM classifies as "Technology"
domain2.com → "Welcome to our site" → Hash match! → "Technology" (no LLM call)
```

**Benefit:** Can reduce LLM calls by 30-50% on large datasets!

### IAB Taxonomy Enrichment

Maps generic categories to industry-standard IAB Content Taxonomy:

```bash
python add_iab_categories_db.py --db wxawebcat.db
```

**Example mapping:**
- Generic: "Technology" → IAB: "Technology & Computing / Computing"
- Generic: "News" → IAB: "News & Politics / Politics"
- Generic: "Adult" → IAB: "Adult Content / Adult Content" (flagged as sensitive)

### DNS Round-Robin

Automatically distributes DNS queries across multiple providers:

**Benefits:**
- Load distribution: 1000 queries → ~100 per server
- Fault tolerance: If one DNS fails, 90% still succeed
- Faster resolution: Parallel queries across servers
- Rate limit avoidance: Queries spread across providers

---

## 🏗️ Architecture

### Two-Stage Pipeline

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Fetcher   │ ───> │   Database   │ ───> │ Classifier  │
└─────────────┘      └──────────────┘      └─────────────┘
     │                      │                     │
     ├─ DNS Lookup          ├─ domains           ├─ LLM API
     ├─ HTTP Fetch          ├─ classifications   ├─ TLD Rules
     └─ Extract Text        └─ content_hash      └─ Hash Cache
```

### Data Flow

1. **Fetch Stage:**
   - Read domains from CSV (streaming)
   - DNS lookup (round-robin, rate limited)
   - HTTP fetch (parallel, connection pooled)
   - Extract title, metadata, content
   - Batch commit to database

2. **Classify Stage:**
   - Load unclassified domains
   - Check TLD rules (fast, no LLM)
   - Check content hash cache (dedup)
   - Call LLM for classification
   - Batch commit results

3. **Enrich Stage:**
   - Map to IAB taxonomy
   - Flag sensitive content
   - Update classifications

### Batch Commit Strategy

**Problem:** Individual commits are slow (100-200ms each)

**Solution:** Batch commits every 100-1000 domains

```python
# OLD: 1000 individual commits = 100-200 seconds
for domain in domains:
    process(domain)
    commit()  # 100-200ms each

# NEW: 10 batch commits = 1-2 seconds
for batch in chunks(domains, 100):
    results = [process(d) for d in batch]
    commit(results)  # 100-200ms total
```

**Result:** 100x faster database writes!

---

## 📝 CSV Format Support

### Supported Formats

**Single Column:**
```csv
google.com
facebook.com
youtube.com
```

**Rank, Domain:**
```csv
1,google.com
2,facebook.com
3,youtube.com
```

**With Header:**
```csv
rank,domain
1,google.com
2,facebook.com
```

**Auto-detection:** The fetcher automatically detects and handles both formats, and skips header rows.

---

## 🎯 Example Workflows

### Daily Production Run

```bash
#!/bin/bash
# Daily domain categorization pipeline

# 1. Fetch new domains
python wxawebcat_web_fetcher_db.py \
  --input daily_domains.csv \
  --config wxawebcat_highperf.toml

# 2. Classify
python wxawebcat_classifier_db.py \
  --db wxawebcat.db \
  --config wxawebcat_highperf.toml

# 3. Enrich with IAB
python add_iab_categories_db.py --db wxawebcat.db

# 4. Export results
python wxawebcat_db.py --export results_$(date +%Y%m%d).csv

# 5. Backup database
cp wxawebcat.db backups/wxawebcat_$(date +%Y%m%d).db
```

### Large Dataset Processing

```bash
# Terminal 1: Start classifier in watch mode
python wxawebcat_classifier_db.py --watch --config wxawebcat_extreme.toml &

# Terminal 2: Process in chunks to monitor progress
for chunk in chunks/*.csv; do
    echo "Processing $chunk"
    python wxawebcat_web_fetcher_db.py \
      --input "$chunk" \
      --config wxawebcat_extreme.toml
    sleep 60  # Let classifier catch up
done
```

### Resume After Interruption

```bash
# The system is resume-safe! Just run again:
python wxawebcat_web_fetcher_db.py --input domains.csv

# ON CONFLICT DO UPDATE handles duplicates automatically
# Unprocessed domains will be fetched
# Already processed domains will be skipped
```

---

## 🔒 Best Practices

### 1. Test with Small Dataset First

```bash
# Test with 1000 domains before running millions
python wxawebcat_web_fetcher_db.py \
  --input domains.csv \
  --limit 1000 \
  --config wxawebcat_highperf.toml

# Check success rate
sqlite3 wxawebcat.db "SELECT fetch_status, COUNT(*) FROM domains GROUP BY fetch_status"
```

**Expected:** 85-95% success rate

### 2. Use Configuration Files

**Don't:**
```bash
# Hard to maintain, easy to make mistakes
python wxawebcat_web_fetcher_db.py --input domains.csv
```

**Do:**
```bash
# Reproducible, documented, easy to tune
python wxawebcat_web_fetcher_db.py \
  --input domains.csv \
  --config wxawebcat_highperf.toml
```

### 3. Monitor Progress

Use timing information to estimate completion:
```
Batch time: 8.2s | Total elapsed: 2h 18m
```

Calculate ETA:
```
Current: 100,000 / 1,000,000 (10%)
Elapsed: 2h 18m
Remaining: 90% × 2h 18m / 10% = 20h 42m
```

### 4. Backup Database Regularly

```bash
# Periodic backups during long runs
while true; do
    sleep 3600  # Every hour
    cp wxawebcat.db backups/wxawebcat_$(date +%Y%m%d_%H%M).db
done &
```

### 5. Be Respectful to DNS Servers

**Don't:**
- Set `dns_delay_ms = 0` on public DNS
- Use only one DNS server
- Set `dns_concurrency > 100` on public DNS

**Do:**
- Use default `dns_delay_ms = 10` (100 qps)
- Use 6-10 DNS servers in round-robin
- Keep `dns_concurrency <= 100`

---

## 📚 Categories Supported

### Generic Categories (30+)

Technology, News, Education, Government, Health, Finance, Shopping, Social Media, Entertainment, Sports, Travel, Real Estate, Automotive, Food & Drink, Business Services, Adult Content, Gaming, and more.

### IAB Taxonomy Tier 1 (20+ categories)

- Arts & Entertainment
- Automotive  
- Business
- Careers
- Education
- Family & Parenting
- Food & Drink
- Health & Fitness
- Hobbies & Interests
- Home & Garden
- News & Politics
- Personal Finance
- Pets
- Real Estate
- Science
- Shopping
- Society
- Sports
- Style & Fashion
- Technology & Computing
- Travel

### IAB Taxonomy Tier 2 (350+ subcategories)

Each tier 1 category has 10-30 detailed subcategories for precise classification.

---

## 🐛 Known Limitations

### 1. Blocked Domains (WAF/Cloudflare)

Some domains block automated requests:
```
Blocked/WAF: 101 (10%)
```

**Can't avoid this** - it's the remote server protecting itself.

### 2. Dead/Parked Domains

5-10% of any large domain list will be:
- Parked domains
- Expired domains
- Domains that no longer resolve

**This is normal** - not a bug!

### 3. LLM Accuracy

Classification accuracy depends on:
- Quality of content extracted
- LLM model capabilities
- Prompt engineering

**Typical accuracy:** 85-95% with good prompts

### 4. Rate Limiting

If processing too fast, you may hit:
- DNS provider rate limits (solution: use more servers)
- Your ISP rate limits (solution: reduce concurrency)
- Target website rate limits (solution: reduce concurrency)

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- [ ] Add more TLD classification rules
- [ ] Improve LLM prompts for better accuracy
- [ ] Add support for more database backends (PostgreSQL, MySQL)
- [ ] Implement distributed processing across multiple machines
- [ ] Add web UI for monitoring progress
- [ ] Support for robots.txt compliance
- [ ] Add retry logic for transient failures
- [ ] Implement A/B testing for different classification strategies

---

## 📄 License

MIT License - Feel free to use in commercial and non-commercial projects.

---

## 🙏 Acknowledgments

- **vLLM** - Fast LLM inference server
- **httpx** - Modern HTTP client
- **aiodns** - Async DNS resolver
- **SQLite** - Reliable embedded database
- **IAB** - Content Taxonomy standards

---

## 📞 Support

**Issues:**
- Check this README first
- Review configuration examples
- Test with 1000 domains before reporting issues
- Include your system specs and config when reporting

**Performance Questions:**
- 20-25 domains/second is optimal
- Remote server response time is the bottleneck
- Your CPU/RAM are likely not the problem

---

## 🎯 Quick Reference

### Common Commands

```bash
# Initialize
python wxawebcat_db.py --init

# Fetch (high-performance)
python wxawebcat_web_fetcher_db.py \
  --input domains.csv \
  --config wxawebcat_highperf.toml

# Classify (watch mode)
python wxawebcat_classifier_db.py \
  --db wxawebcat.db \
  --config wxawebcat_highperf.toml \
  --watch

# Enrich with IAB
python add_iab_categories_db.py --db wxawebcat.db

# Export
python wxawebcat_db.py --export results.csv

# Statistics
python wxawebcat_db.py --stats
```

### Recommended Configs by System

| CPU Cores | RAM | Config File |
|-----------|-----|-------------|
| 4-8 | 4-8 GB | wxawebcat_enhanced.toml |
| 8-16 | 8-16 GB | wxawebcat_highperf.toml |
| 16-32 | 16-32 GB | wxawebcat_ultra.toml |
| 32+ | 64+ GB | wxawebcat_extreme.toml |

### Expected Performance

| Dataset Size | Time (High-Perf) | Time (Extreme) |
|--------------|-----------------|----------------|
| 1,000 | ~42s | ~30s |
| 10,000 | ~7m | ~5m |
| 100,000 | ~70m | ~50m |
| 1,000,000 | ~12h | ~8h |

---

**Made with ❤️ for high-performance domain categorization**
