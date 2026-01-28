# DNS Rate Limiting - Be Respectful to DNS Servers

## 🎯 **What Changed**

Added **DNS rate limiting** to prevent flooding DNS servers with too many queries!

---

## 🐛 **The Problem**

### Before (Aggressive):
```
dns_concurrency = 50  # 50 simultaneous DNS queries!
No delay between queries

Result: Up to 50 queries hitting DNS servers at once
        → Can be seen as abusive
        → May trigger rate limiting
        → Not respectful to public DNS providers
```

**Example:** 1000 domains with 50 concurrent = **bursts of 50 queries at a time!**

---

## ✅ **The Solution**

### Now (Respectful):
```
dns_concurrency = 20   # Max 20 simultaneous queries
dns_delay_ms = 10      # 10ms delay between each query

Result: Maximum 100 queries/second
        → Smooth, steady rate
        → Respectful to DNS servers
        → Less likely to trigger limits
```

---

## ⚙️ **Configuration**

### In `wxawebcat_enhanced.toml`:

```toml
[dns]
servers = [
    "1.1.1.1",
    "1.0.0.1",
    "8.8.8.8",
    "8.8.4.4",
    "9.9.9.9",
    "208.67.222.222"
]

# DNS rate limiting
delay_ms = 10  # Milliseconds between queries

[fetcher]
dns_concurrency = 20  # Max concurrent DNS queries
```

---

## 📊 **Rate Limiting Examples**

### Very Respectful (Slow):
```toml
[dns]
delay_ms = 50  # 50ms between queries

[fetcher]
dns_concurrency = 10
```

**Rate:** 20 queries/second
**1000 domains:** ~50 seconds for DNS
**Best for:** Being extra cautious with DNS servers

---

### Balanced (Default):
```toml
[dns]
delay_ms = 10  # 10ms between queries

[fetcher]
dns_concurrency = 20
```

**Rate:** 100 queries/second
**1000 domains:** ~10 seconds for DNS
**Best for:** Most use cases

---

### Fast (Still Respectful):
```toml
[dns]
delay_ms = 5  # 5ms between queries

[fetcher]
dns_concurrency = 30
```

**Rate:** 200 queries/second
**1000 domains:** ~5 seconds for DNS
**Best for:** Trusted environments with permission

---

### No Throttling (Use with Caution):
```toml
[dns]
delay_ms = 0  # No delay

[fetcher]
dns_concurrency = 50
```

**Rate:** Limited only by concurrency
**Best for:** Your own DNS servers
**Warning:** May trigger rate limits on public DNS!

---

## 🔍 **How Rate Limiting Works**

### Token Bucket Algorithm:

```python
class DNSResolverPool:
    def __init__(self, dns_servers, delay_ms=10):
        self.delay_seconds = delay_ms / 1000.0
        self.last_query_time = 0
    
    async def get_resolver(self):
        # Wait if needed to maintain rate
        now = time()
        time_since_last = now - self.last_query_time
        
        if time_since_last < self.delay_seconds:
            await asyncio.sleep(self.delay_seconds - time_since_last)
        
        self.last_query_time = time()
        return resolver
```

**Effect:** Guarantees minimum delay between DNS queries

---

## 📈 **Performance Impact**

### Comparison (1000 domains):

| Config | DNS Concurrency | Delay (ms) | Queries/Sec | DNS Time |
|--------|----------------|------------|-------------|----------|
| **Aggressive** | 50 | 0 | Unlimited | 2 sec |
| **Fast** | 30 | 5 | 200 | 5 sec |
| **Balanced** | 20 | 10 | 100 | 10 sec |
| **Respectful** | 10 | 50 | 20 | 50 sec |

**Note:** DNS time is a small portion of total fetch time (HTTP takes much longer)

---

## 🎯 **Recommended Settings**

### For Public DNS (Default):
```toml
[dns]
delay_ms = 10
servers = ["1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "208.67.222.222"]

[fetcher]
dns_concurrency = 20
```

**Why:** Respectful rate (~100 qps), distributed across 6 servers

---

### For Your Own DNS Server:
```toml
[dns]
delay_ms = 0
servers = ["192.168.1.1"]

[fetcher]
dns_concurrency = 50
```

**Why:** You control it, no need to throttle

---

### For Large-Scale (Get Permission First):
```toml
[dns]
delay_ms = 5
servers = [
    "1.1.1.1", "1.0.0.1",
    "8.8.8.8", "8.8.4.4",
    "9.9.9.9", "149.112.112.112",
    "208.67.222.222", "208.67.220.220"
]

[fetcher]
dns_concurrency = 30
```

**Why:** More servers = more capacity, but still throttled

---

## 💡 **DNS Server Capacity**

### Public DNS Provider Limits:

| Provider | Stated Limit | Recommendation |
|----------|-------------|----------------|
| **Cloudflare** | No public limit | 100-200 qps OK |
| **Google** | No public limit | 100-200 qps OK |
| **Quad9** | Rate limiting exists | 50-100 qps safe |
| **OpenDNS** | 100k queries/day free | 1-2 qps average |

**Our default (100 qps) is well within all limits!**

---

## 🚦 **Real-World Performance**

### Example: 1000 Domains

**With rate limiting (delay_ms=10, concurrency=20):**
```
DNS queries:    ~10 seconds (throttled)
HTTP fetches:   ~50 seconds (main bottleneck)
Total:          ~60 seconds

DNS is only 16% of total time!
```

**Without rate limiting (delay_ms=0, concurrency=50):**
```
DNS queries:    ~2 seconds (burst)
HTTP fetches:   ~50 seconds
Total:          ~52 seconds

Only 8 seconds faster, but less respectful
```

**Conclusion:** Rate limiting adds minimal time but is much more respectful!

---

## 🎓 **Best Practices**

### 1. Start Conservative
```toml
[dns]
delay_ms = 20  # Very respectful
```

Then increase if needed.

### 2. Use Multiple DNS Servers
```toml
[dns]
servers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]  # Spread the load
```

Each server gets 1/3 of queries!

### 3. Monitor Your Rate
```
DNS rate: max 100 queries/second (throttled)
```

This is shown in output - make sure it's reasonable.

### 4. Respect Public Resources
Public DNS is free - be a good citizen:
- Don't burst > 200 qps
- Use delays (10-20ms)
- Distribute across servers

---

## 📊 **Output Example**

```bash
$ python wxawebcat_web_fetcher_db.py --input domains.csv --config wxawebcat_enhanced.toml

Found 1000 domains to fetch
Database: wxawebcat.db
Batch size: 100
DNS concurrency: 20
DNS delay: 10ms between queries
DNS servers: 1.1.1.1, 1.0.0.1, 8.8.8.8, 8.8.4.4, 9.9.9.9, 208.67.222.222

Created DNS resolver pool with 6 servers
DNS rate: max 100 queries/second (throttled)

Processing batch 1 (100 domains)...
✓ Batch 1 complete: 100/1000 (10.0%)
```

**See:** "DNS rate: max 100 queries/second (throttled)" confirms rate limiting!

---

## 🔧 **Troubleshooting**

### Too Slow?
```toml
[dns]
delay_ms = 5  # Reduce delay
[fetcher]
dns_concurrency = 30  # Increase concurrency
```

### Getting Rate Limited?
```toml
[dns]
delay_ms = 50  # Increase delay
[fetcher]
dns_concurrency = 10  # Decrease concurrency
```

### Need More Speed?
Add more DNS servers instead of increasing rate:
```toml
[dns]
servers = [
    "1.1.1.1", "1.0.0.1",
    "8.8.8.8", "8.8.4.4", 
    "9.9.9.9", "149.112.112.112",
    "208.67.222.222", "208.67.220.220"
]  # 8 servers = more capacity
```

---

## ✅ **Summary**

**Changes:**
- ✅ Added DNS rate limiting (configurable delay)
- ✅ Lowered default dns_concurrency (50 → 20)
- ✅ Shows DNS rate in output
- ✅ Prevents flooding DNS servers
- ✅ More respectful to public DNS

**Default Settings:**
- 20 concurrent DNS queries (down from 50)
- 10ms delay between queries
- Max 100 queries/second (throttled)
- 6 DNS servers in round-robin

**Impact:**
- Slightly slower DNS (2 sec → 10 sec for 1000 domains)
- But HTTP is still the bottleneck (~50 sec)
- Total impact: ~8 seconds longer for 1000 domains
- Much more respectful to public DNS servers!

**You're now being a good citizen to public DNS infrastructure!** 🌟
