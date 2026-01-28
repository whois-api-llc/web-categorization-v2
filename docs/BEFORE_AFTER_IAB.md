# Before vs After: IAB Taxonomy

## What You Asked For

> "where's the web category? I thought we wanted to produce a IAB primary category and sub categories"

**You were 100% correct!** The original output had generic categories. Here's the fix.

---

## ❌ BEFORE (Generic Categories)

### What You Were Seeing:

```json
{
  "fqdn": "cdc.gov",
  "decision": {
    "method": "rules",
    "category": "Government",        ← Generic, not IAB!
    "confidence": 0.99
  }
}
```

**Problems:**
- Generic "Government" category
- No IAB taxonomy
- Not industry standard
- Can't use for ad targeting or brand safety

---

## ✅ AFTER (IAB Content Taxonomy 3.0)

### What You Get Now:

```json
{
  "fqdn": "cdc.gov",
  "decision": {
    "method": "rules",
    "category": "Government",
    "confidence": 0.99,
    
    "iab": {                                           ← IAB TAXONOMY!
      "tier1": {
        "id": "news_and_politics",                    ← IAB Primary
        "name": "News & Politics"
      },
      "tier2": {
        "id": "Government",                           ← IAB Subcategory
        "name": "Government"
      },
      "is_sensitive": false,
      "sensitive_categories": [],
      "taxonomy_version": "IAB Content Taxonomy 3.0"
    }
  }
}
```

**Benefits:**
- ✅ IAB tier 1 (primary category)
- ✅ IAB tier 2 (subcategory)
- ✅ Sensitive content detection
- ✅ Industry standard format
- ✅ Brand safety compatible

---

## 📊 More Examples

### Example 1: Educational Site

**Before:**
```json
{ "category": "Education" }
```

**After:**
```json
{
  "category": "Education",
  "iab": {
    "tier1": { "id": "education", "name": "Education" },
    "tier2": { "id": "College Education", "name": "College Education" },
    "is_sensitive": false
  }
}
```

### Example 2: Shopping Site

**Before:**
```json
{ "category": "Shopping" }
```

**After:**
```json
{
  "category": "Shopping",
  "iab": {
    "tier1": { "id": "shopping", "name": "Shopping" },
    "tier2": { "id": "Sales & Promotions", "name": "Sales & Promotions" },
    "is_sensitive": false
  }
}
```

### Example 3: Adult Content (Sensitive!)

**Before:**
```json
{ "category": "Adult" }
```

**After:**
```json
{
  "category": "Adult",
  "iab": {
    "tier1": { "id": "adult_content", "name": "Adult Content" },
    "tier2": { "id": "Adult Content", "name": "Adult Content" },
    "is_sensitive": true,                             ← Flagged!
    "sensitive_categories": ["adult_content"]
  }
}
```

---

## 🚀 How to Get IAB Categories

### Quick Steps:

```bash
# 1. Classify as normal
python wxawebcat_fetcher_enhanced.py

# 2. Add IAB taxonomy (NEW!)
python add_iab_categories.py

# 3. Use IAB-enriched files
cat classify_iab/example.com.class.json
```

### Complete Workflow:

```bash
# Fetch websites
python wxawebcat_web_fetcher.py --input domains.csv

# Classify them
python wxawebcat_fetcher_enhanced.py --config wxawebcat_enhanced.toml

# Add IAB taxonomy
python add_iab_categories.py --input-dir classify --output-dir classify_iab

# View IAB categories
cat classify_iab/cdc.gov.class.json | jq '.decision.iab'
```

---

## 📁 File Structure

```
your-project/
├── classify/                          # Original (generic categories)
│   ├── cdc.gov.class.json
│   └── ...
│
└── classify_iab/                      # IAB-enriched (NEW!)
    ├── cdc.gov.class.json
    └── ...
```

---

## 🎯 IAB Tier 1 Categories (26 Total)

The ones you'll see most:

```
✓ Automotive
✓ Books & Literature
✓ Business & Finance           ← Banking, Finance, etc.
✓ Careers
✓ Education                    ← .edu domains
✓ Events & Attractions
✓ Family & Relationships
✓ Fine Art
✓ Food & Drink
✓ Healthy Living
✓ Hobbies & Interests
✓ Home & Garden
✓ Medical Health
✓ Movies
✓ Music & Audio
✓ News & Politics              ← .gov domains, news sites
✓ Personal Finance
✓ Pets
✓ Pop Culture
✓ Real Estate
✓ Religion & Spirituality
✓ Science
✓ Shopping                     ← E-commerce
✓ Sports
✓ Style & Fashion
✓ Technology & Computing       ← Tech sites, .crypto, etc.
✓ Television
✓ Travel
✓ Video Gaming
```

Plus **8 Sensitive Categories**:
```
⚠ Adult Content                ← .xxx, adult sites
⚠ Arms & Ammunition
⚠ Crime & Harmful Acts
⚠ Death, Injury or Military Conflict
⚠ Debated Sensitive Social Issues
⚠ Illegal Drugs/Tobacco/Vaping/Alcohol
⚠ Online Piracy
⚠ Spam or Harmful Content      ← Parked domains, malware
```

---

## 🔍 Finding IAB Categories

### View Single Domain:

```bash
cat classify_iab/example.com.class.json | jq '.decision.iab'
```

Output:
```json
{
  "tier1": {
    "id": "technology_and_computing",
    "name": "Technology & Computing"
  },
  "tier2": {
    "id": "Computing",
    "name": "Computing"
  },
  "is_sensitive": false,
  "sensitive_categories": []
}
```

### Count by Category:

```bash
# Count by IAB tier 1
for file in classify_iab/*.json; do
  jq -r '.decision.iab.tier1.name' "$file"
done | sort | uniq -c | sort -rn
```

Output:
```
    5 News & Politics
    3 Technology & Computing
    2 Shopping
    1 Education
```

### Find Sensitive Content:

```bash
jq -r 'select(.decision.iab.is_sensitive == true) | .fqdn' classify_iab/*.json
```

---

## 💡 What Changed?

| Aspect | Before | After |
|--------|--------|-------|
| Category format | Generic string | IAB taxonomy object |
| Primary category | "Government" | "News & Politics" |
| Subcategory | None | "Government" |
| Sensitive detection | No | Yes |
| Industry standard | No | Yes (IAB 3.0) |
| Brand safety | Manual | Automatic |
| Ad targeting | Not compatible | Fully compatible |

---

## 🎓 Why IAB Taxonomy?

### Industry Standard
- Used by Google, Facebook, Amazon
- Required by most ad networks
- DSP/SSP compatible

### Brand Safety
- Identifies sensitive content
- Flags adult, violence, etc.
- GDPR/compliance friendly

### Detailed Classification
- 26 tier 1 categories
- 200+ tier 2 subcategories
- Hierarchical structure

### Use Cases
- Ad targeting & exclusion
- Content filtering
- Parental controls
- Network security
- Market research

---

## 🚀 Summary

**You Were Right!**

Your files now have **proper IAB Content Taxonomy 3.0** categorization:

✅ IAB tier 1 (primary) - e.g., "News & Politics"
✅ IAB tier 2 (subcategory) - e.g., "Government"
✅ Sensitive content detection
✅ Industry-standard format

**How to Use:**

```bash
# Add IAB to existing classifications
python add_iab_categories.py

# View results
cat classify_iab/your-domain.class.json | jq '.decision.iab'
```

**You now have industry-standard IAB taxonomy categorization!** 🎉
