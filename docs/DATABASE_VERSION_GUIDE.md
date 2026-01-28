# wxawebcat Database Version - Complete Guide

## 🎯 **What Changed**

**BEFORE (File-based):**
```
domains.csv → fetch/*.json → classify/*.json → classify_iab/*.json
```

**AFTER (Database):**
```
domains.csv → SQLite database (all data in one place)
```

---

## 🗄️ **Database Schema**

### Tables:

1. **domains** - Stores fetch results
   - fqdn, dns_data, http_data
   - fetch_status, classified (boolean)
   - Timestamps

2. **classifications** - Stores classification results
   - domain_id (foreign key)
   - method, category, confidence
   - IAB taxonomy fields
   - Content hash for deduplication

3. **content_hash_cache** - Deduplication cache
   - content_hash → category mapping
   - Tracks hit_count for stats

---

## 🚀 **Quick Start (3 Commands)**

### Step 1: Initialize Database

```bash
python wxawebcat_db.py --init
```

**Output:**
```
Initializing database: wxawebcat.db
✓ Database initialized: wxawebcat.db
```

### Step 2: Fetch Websites

```bash
python wxawebcat_web_fetcher_db.py --input domains.csv
```

**What it does:**
- Reads domains from CSV
- Fetches DNS + HTTP data
- **Stores in database** (not files!)
- Marks as `classified = 0`

### Step 3: Classify Domains

```bash
python wxawebcat_classifier_db.py --db wxawebcat.db
```

**What it does:**
- Reads unclassified domains from database
- Applies TLD rules + content hash
- Calls LLM for remaining domains
- **Updates database** with classifications
- Marks domains as `classified = 1`

### Step 4 (Optional): Add IAB Taxonomy

```bash
python add_iab_categories_db.py --db wxawebcat.db
```

**What it does:**
- Reads classifications from database
- Adds IAB tier1/tier2 categories
- Detects sensitive content
- **Updates records in place**
- Marks as `iab_enriched = 1`

---

## 📊 **Database Workflow**

```
┌─────────────────┐
│  domains.csv    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FETCH           │ → INSERT INTO domains
│ (Step 2)        │   (classified=0)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ CLASSIFY        │ → INSERT INTO classifications
│ (Step 3)        │   UPDATE domains SET classified=1
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ IAB ENRICH      │ → UPDATE classifications
│ (Step 4)        │   SET iab_tier1_*, iab_enriched=1
└─────────────────┘
```

---

## 🔍 **Querying the Database**

### View Statistics

```bash
python wxawebcat_db.py --stats --db wxawebcat.db
```

**Output:**
```
=== DATABASE STATISTICS ===
Total domains:        1000
Classified:           1000
Unclassified:         0
Failed fetches:       0

Total classifications: 1000
IAB enriched:         1000

By method:
  rules           450
  llm             350
  hash_cache      200
```

### Export to CSV

```bash
python wxawebcat_db.py --export results.csv --db wxawebcat.db
```

**Output:** `results.csv` with all classifications

### Direct SQL Queries

```bash
sqlite3 wxawebcat.db
```

```sql
-- View all classifications
SELECT * FROM classified_with_iab;

-- Count by category
SELECT category, COUNT(*) FROM classifications GROUP BY category;

-- Top IAB tier 1 categories
SELECT iab_tier1_name, COUNT(*) as count 
FROM classifications 
WHERE iab_tier1_name IS NOT NULL 
GROUP BY iab_tier1_name 
ORDER BY count DESC;

-- Find sensitive content
SELECT fqdn, category, sensitive_categories 
FROM classifications 
WHERE is_sensitive = 1;

-- Classification methods breakdown
SELECT * FROM classification_by_method;

-- Unclassified domains
SELECT fqdn, fetch_status 
FROM domains 
WHERE classified = 0;
```

---

## 💾 **Database Operations**

### Backup Database

```bash
sqlite3 wxawebcat.db ".backup wxawebcat_backup.db"
```

### Vacuum/Optimize

```bash
sqlite3 wxawebcat.db "VACUUM; ANALYZE;"
```

### Check Database Size

```bash
ls -lh wxawebcat.db
```

### Reset Classifications (Keep Fetch Data)

```sql
DELETE FROM classifications;
UPDATE domains SET classified = 0, classified_at = NULL;
```

### Reset Everything

```bash
rm wxawebcat.db
python wxawebcat_db.py --init
```

---

## 🎯 **Advantages Over File-Based**

| Aspect | File-Based | Database |
|--------|------------|----------|
| Storage | 1000s of JSON files | Single .db file |
| Resume | Check file existence | Query `classified = 0` |
| Dedup | Separate cache file | Built-in cache table |
| Queries | grep/jq/python | SQL queries |
| Concurrent access | File locks | Row-level locks |
| Indexing | None | Automatic indexes |
| Stats | Count files | `SELECT COUNT(*)` |
| Export | Multiple files | Single CSV |
| Backup | Tar folder | Copy one file |

---

## 📁 **File Structure**

```
your-project/
├── domains.csv                        # Input
├── wxawebcat.db                       # DATABASE (all data!)
│
├── wxawebcat_db.py                    # Database utilities
├── schema.sql                         # Database schema
├── wxawebcat_web_fetcher_db.py       # Fetcher (writes to DB)
├── wxawebcat_classifier_db.py        # Classifier (reads/writes DB)
├── add_iab_categories_db.py          # IAB enrichment (updates DB)
│
└── wxawebcat_enhanced.toml           # Configuration
```

---

## 🔧 **Configuration**

Same TOML config works for database version:

```toml
[llm]
base_url = "http://127.0.0.1:8000/v1"
model = "Qwen/Qwen2.5-7B-Instruct"
llm_concurrency = 32
max_tokens = 150

[tld_rules]
enabled = true

[content_hash]
enabled = true
```

---

## 📊 **Example Workflow**

### Process 1000 Domains

```bash
# Initialize
python wxawebcat_db.py --init

# Fetch
python wxawebcat_web_fetcher_db.py --input top1000.csv
# → 1000 domains in database, classified=0

# Classify
python wxawebcat_classifier_db.py
# → 1000 classifications added, domains marked classified=1

# Add IAB
python add_iab_categories_db.py
# → All classifications updated with IAB taxonomy

# Export results
python wxawebcat_db.py --export results.csv

# View stats
python wxawebcat_db.py --stats
```

### Incremental Processing

```bash
# Day 1: Fetch batch 1
python wxawebcat_web_fetcher_db.py --input batch1.csv

# Day 1: Classify
python wxawebcat_classifier_db.py

# Day 2: Fetch batch 2 (adds to same DB)
python wxawebcat_web_fetcher_db.py --input batch2.csv

# Day 2: Classify (only processes new domains)
python wxawebcat_classifier_db.py

# Final export (includes all batches)
python wxawebcat_db.py --export all_results.csv
```

---

## 🎓 **Database Schema Details**

### domains Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| fqdn | TEXT | Domain name (unique) |
| dns_data | TEXT | JSON: DNS records |
| http_data | TEXT | JSON: HTTP response |
| fetched_at | TEXT | ISO timestamp |
| fetch_status | TEXT | success/dns_failed/http_failed/blocked |
| classified | INTEGER | 0=no, 1=yes |
| classified_at | TEXT | ISO timestamp |

### classifications Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| domain_id | INTEGER | FK to domains.id |
| fqdn | TEXT | Domain name (denormalized) |
| method | TEXT | rules/llm/hash_cache |
| category | TEXT | Generic category |
| confidence | REAL | 0.0 to 1.0 |
| iab_tier1_id | TEXT | IAB primary category ID |
| iab_tier1_name | TEXT | IAB primary category name |
| iab_tier2_id | TEXT | IAB subcategory ID |
| iab_tier2_name | TEXT | IAB subcategory name |
| is_sensitive | INTEGER | 0=no, 1=yes |
| content_hash | TEXT | SHA-256 for dedup |
| iab_enriched | INTEGER | 0=no, 1=yes |

---

## 🚀 **Performance**

### Database Size

```
1,000 domains:    ~1-2 MB
10,000 domains:   ~10-20 MB
100,000 domains:  ~100-200 MB
1,000,000 domains: ~1-2 GB
```

### Query Speed

```
SELECT with indexes:   <1ms
Bulk INSERT (1000):    ~100ms
UPDATE (1000):         ~50ms
Complex JOINs:         ~10ms
```

### Concurrent Access

SQLite supports:
- Multiple readers simultaneously
- One writer at a time
- Automatic locking

---

## 🔍 **Troubleshooting**

### "database is locked"

**Cause:** Another process is writing

**Fix:** Wait or increase timeout
```python
conn = sqlite3.connect(db_path, timeout=30.0)
```

### "no such table: domains"

**Cause:** Database not initialized

**Fix:**
```bash
python wxawebcat_db.py --init
```

### "UNIQUE constraint failed"

**Cause:** Domain already exists

**Fix:** This is OK - it's updating the existing record

---

## 💡 **Best Practices**

1. **Backup regularly**
   ```bash
   cp wxawebcat.db wxawebcat_backup_$(date +%Y%m%d).db
   ```

2. **Vacuum periodically**
   ```bash
   sqlite3 wxawebcat.db "VACUUM;"
   ```

3. **Use transactions for bulk operations**
   ```python
   with get_connection() as conn:
       # All operations in one transaction
       ...
   ```

4. **Index important columns**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_custom ON table(column);
   ```

5. **Monitor database size**
   ```bash
   du -h wxawebcat.db
   ```

---

## ✅ **Summary**

**Benefits:**
- ✅ Single file storage
- ✅ Fast SQL queries
- ✅ Built-in deduplication
- ✅ Easy statistics
- ✅ Incremental processing
- ✅ Concurrent access safe
- ✅ IAB in-place updates

**Commands:**
```bash
# Initialize
python wxawebcat_db.py --init

# Fetch
python wxawebcat_web_fetcher_db.py --input domains.csv

# Classify
python wxawebcat_classifier_db.py

# Add IAB
python add_iab_categories_db.py

# Export
python wxawebcat_db.py --export results.csv
```

**You now have a production-ready database system!** 🎉
