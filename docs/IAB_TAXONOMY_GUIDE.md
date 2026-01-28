# IAB Content Taxonomy Integration Guide

## 🎯 What You Need

You're **100% correct** - for web categorization, you need **IAB (Interactive Advertising Bureau) taxonomy**, not generic categories!

**Before (Generic):**
```json
{
  "category": "Government"
}
```

**After (IAB Taxonomy 3.0):**
```json
{
  "category": "Government",
  "generic_category": "Government",
  "iab": {
    "tier1": {
      "id": "news_and_politics",
      "name": "News & Politics"
    },
    "tier2": {
      "id": "Government",
      "name": "Government"
    },
    "is_sensitive": false,
    "sensitive_categories": [],
    "taxonomy_version": "IAB Content Taxonomy 3.0"
  }
}
```

---

## 🚀 Quick Start

### Option 1: Add IAB to Existing Classifications (Easiest)

```bash
# 1. Run classifier as normal
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# 2. Add IAB taxonomy
python add_iab_categories.py --input-dir classify --output-dir classify_iab

# 3. Use IAB-enriched files
ls classify_iab/
```

### Option 2: Integrated Workflow

```bash
# Fetch
python wxawebcat_web_fetcher.py --input domains.csv

# Classify
python wxawebcat_fetcher_enhanced.py

# Add IAB
python add_iab_categories.py

# Done! IAB categories in classify_iab/
```

---

## 📊 IAB Taxonomy Structure

### Tier 1 Categories (Primary - 26 categories)

```
Automotive
Books & Literature
Business & Finance
Careers
Education
Events & Attractions
Family & Relationships
Fine Art
Food & Drink
Healthy Living
Hobbies & Interests
Home & Garden
Medical Health
Movies
Music & Audio
News & Politics
Personal Finance
Pets
Pop Culture
Real Estate
Religion & Spirituality
Science
Shopping
Sports
Style & Fashion
Technology & Computing
Television
Travel
Video Gaming
```

### Tier 2 Categories (Subcategories)

**Example - Technology & Computing:**
- Artificial Intelligence
- Augmented Reality
- Cloud Computing
- Cybersecurity
- Computing
- Consumer Electronics
- Databases
- IT & Internet Support
- Mobile Apps & Services
- Network Security
- Programming
- Robotics
- Social Networking
- Virtual Reality
- Web Development

### Sensitive Categories

```
Adult Content
Arms & Ammunition
Crime & Harmful Acts
Death, Injury or Military Conflict
Debated Sensitive Social Issues
Illegal Drugs/Tobacco/e-Cigarettes/Vaping/Alcohol
Online Piracy
Spam or Harmful Content
```

---

## 🗺️ Category Mapping

### Generic → IAB Mapping

| Generic Category | IAB Tier 1 | IAB Tier 2 |
|-----------------|------------|------------|
| Government | News & Politics | Government |
| Education | Education | College Education |
| Adult | Adult Content | Adult Content |
| Finance | Business & Finance | Banking |
| Technology | Technology & Computing | Computing |
| Shopping | Shopping | Sales & Promotions |
| News | News & Politics | National News |
| Social | Technology & Computing | Social Networking |
| Games | Video Gaming | Video Gaming |
| Malware/Phishing | Spam or Harmful Content | Malware |

### TLD-Based IAB Mapping

| TLD | IAB Tier 1 | IAB Tier 2 |
|-----|------------|------------|
| .gov | News & Politics | Government |
| .edu | Education | College Education |
| .xxx | Adult Content | Adult Content |
| .bank | Business & Finance | Banking |
| .crypto | Technology & Computing | Computing |

---

## 📁 Output Format

### Complete Example

```json
{
  "fqdn": "cdc.gov",
  "input_file": "cdc.gov.json",
  "ts_classify_utc": "2026-01-28T02:38:12Z",
  "decision": {
    "method": "rules",
    "category": "Government",           # Original
    "generic_category": "Government",    # Same as category
    "confidence": 0.99,
    "reason": "rule: TLD .gov → Government TLD",
    
    "iab": {                            # IAB TAXONOMY ✓
      "tier1": {
        "id": "news_and_politics",
        "name": "News & Politics"
      },
      "tier2": {
        "id": "Government",
        "name": "Government"
      },
      "is_sensitive": false,
      "sensitive_categories": [],
      "taxonomy_version": "IAB Content Taxonomy 3.0"
    }
  },
  "signals": {
    "http_status": 200,
    "content_type": "text/html",
    "title": "Centers for Disease Control"
  }
}
```

---

## 🔧 Using the IAB Converter

### Basic Usage

```bash
python add_iab_categories.py
```

Default paths:
- Input: `./classify/`
- Output: `./classify_iab/`

### Custom Directories

```bash
python add_iab_categories.py \
  --input-dir /path/to/classifications \
  --output-dir /path/to/iab_output
```

### What It Does

1. Reads all `.class.json` files from input directory
2. Maps generic categories to IAB taxonomy
3. Detects sensitive content
4. Adds IAB fields to each classification
5. Writes enriched files to output directory

---

## 📊 Querying IAB Data

### Extract IAB Categories

```bash
# View IAB tier 1
cat classify_iab/example.com.class.json | jq '.decision.iab.tier1'

# View IAB tier 2
cat classify_iab/example.com.class.json | jq '.decision.iab.tier2'

# Check if sensitive
cat classify_iab/example.com.class.json | jq '.decision.iab.is_sensitive'
```

### Aggregate by Category

```bash
# Count by IAB tier 1
for file in classify_iab/*.json; do
  jq -r '.decision.iab.tier1.name' "$file"
done | sort | uniq -c | sort -rn

# Count sensitive content
grep -r '"is_sensitive": true' classify_iab/ | wc -l
```

### Export to CSV

```bash
# Create CSV with IAB categories
echo "domain,tier1,tier2,sensitive" > iab_report.csv
for file in classify_iab/*.json; do
  domain=$(jq -r '.fqdn' "$file")
  tier1=$(jq -r '.decision.iab.tier1.name' "$file")
  tier2=$(jq -r '.decision.iab.tier2.name' "$file")
  sensitive=$(jq -r '.decision.iab.is_sensitive' "$file")
  echo "$domain,$tier1,$tier2,$sensitive" >> iab_report.csv
done
```

---

## 🎯 Real-World Examples

### Example 1: Government Site

```json
{
  "fqdn": "cdc.gov",
  "decision": {
    "category": "Government",
    "iab": {
      "tier1": { "id": "news_and_politics", "name": "News & Politics" },
      "tier2": { "id": "Government", "name": "Government" },
      "is_sensitive": false
    }
  }
}
```

### Example 2: Educational Institution

```json
{
  "fqdn": "mit.edu",
  "decision": {
    "category": "Education",
    "iab": {
      "tier1": { "id": "education", "name": "Education" },
      "tier2": { "id": "College Education", "name": "College Education" },
      "is_sensitive": false
    }
  }
}
```

### Example 3: Adult Content (Sensitive)

```json
{
  "fqdn": "example.xxx",
  "decision": {
    "category": "Adult",
    "iab": {
      "tier1": { "id": "adult_content", "name": "Adult Content" },
      "tier2": { "id": "Adult Content", "name": "Adult Content" },
      "is_sensitive": true,
      "sensitive_categories": ["adult_content"]
    }
  }
}
```

### Example 4: Shopping Site

```json
{
  "fqdn": "amazon.com",
  "decision": {
    "category": "Shopping",
    "iab": {
      "tier1": { "id": "shopping", "name": "Shopping" },
      "tier2": { "id": "Sales & Promotions", "name": "Sales & Promotions" },
      "is_sensitive": false
    }
  }
}
```

---

## 🔄 Integration Options

### Option A: Post-Processing (Current)

```bash
# Classify → Add IAB → Use IAB files
python wxawebcat_fetcher_enhanced.py
python add_iab_categories.py
```

**Pros:**
- ✅ Simple, no changes to classifier
- ✅ Can re-run IAB mapping independently
- ✅ Keep both generic and IAB versions

**Cons:**
- ❌ Extra step
- ❌ Two sets of files

### Option B: Integrated Classifier (Coming Soon)

I can create a version that outputs IAB taxonomy directly from the classifier.

**Pros:**
- ✅ One step
- ✅ Single output format

**Cons:**
- ❌ More complex classifier code

---

## 📈 Use Cases

### Content Filtering

```bash
# Find all adult content
grep -r '"adult_content"' classify_iab/

# Find all sensitive categories
jq -r 'select(.decision.iab.is_sensitive == true) | .fqdn' classify_iab/*.json
```

### Ad Targeting

```bash
# Group by IAB tier 1 for ad categories
for file in classify_iab/*.json; do
  jq -r '.decision.iab.tier1.id' "$file"
done | sort | uniq -c
```

### Compliance & Safety

```bash
# Check for regulated content
jq -r 'select(.decision.iab.sensitive_categories | length > 0) | 
  {domain: .fqdn, categories: .decision.iab.sensitive_categories}' \
  classify_iab/*.json
```

---

## 🎓 IAB Taxonomy Resources

**Official Documentation:**
- https://iabtechlab.com/standards/content-taxonomy/
- IAB Tech Lab Content Taxonomy 3.0

**Key Points:**
- Industry standard for digital advertising
- Used by ad networks, DSPs, SSPs
- Supports brand safety requirements
- Compatible with GDPR and privacy regulations

---

## 💡 Summary

**What You Have Now:**

✅ **Generic categories** (fast, simple)
✅ **IAB Content Taxonomy 3.0** (industry standard)
✅ **Sensitive content detection** (brand safety)
✅ **Both tier 1 and tier 2** (detailed categorization)

**Complete Workflow:**

```bash
# 1. Fetch websites
python wxawebcat_web_fetcher.py --input domains.csv

# 2. Classify them
python wxawebcat_fetcher_enhanced.py

# 3. Add IAB taxonomy
python add_iab_categories.py

# 4. Use IAB-enriched files
cat classify_iab/example.com.class.json | jq '.decision.iab'
```

**You now have proper IAB taxonomy categorization!** 🎉
