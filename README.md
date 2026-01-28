```markdown
# wxawebcat — Web XML API Web Categorization

**wxawebcat** is a high-throughput, resume-safe, two-stage pipeline for categorizing very large lists of fully qualified domain names (FQDNs).  
It decouples **web fetching (I/O-bound)** from **LLM inference (GPU-bound)** to maximize throughput, reliability, and GPU utilization.

The system is designed for **offline fetch + local LLM classification** using **vLLM (OpenAI-compatible API)**, avoiding live fetch latency during inference.

---

## Key Features

- 🚀 **High throughput** via async concurrency
- 🔁 **Resume-safe & deduplicated** (fetch and classify independently)
- 🧠 **Local LLM inference** (no external API dependency)
- 🧹 **Rule-based pre-classification** removes 60–90% of LLM calls
- 🧱 **WAF / bot detection handling** with Playwright and curl-impersonate fallbacks
- 🧭 **Canonical category normalization** (LLM → stable taxonomy)
- 📦 **One JSON per FQDN** (easy parallelism and auditing)
- ⚙️ **Fully configurable via TOML + CLI overrides**

---

## Architecture Overview

```

CSV (FQDN list)
│
▼
┌──────────────────────────┐
│ FETCH STAGE               │  wxawebcat_fetcher.py
│---------------------------│
│ - Async DNS + HTTP fetch  │
│ - Block/WAF detection     │
│ - Optional TLS capture    │
│ - Resume-safe             │
│ - Output: ./fetch/*.json  │
└──────────────────────────┘
│
▼
┌──────────────────────────┐
│ CLASSIFY STAGE            │  wxawebcat.py
│---------------------------│
│ - Rule-based filtering    │
│ - Local vLLM inference    │
│ - Category normalization  │
│ - Resume-safe             │
│ - Output: ./classify/*.json
└──────────────────────────┘

````

---

## Input

- **Single-column CSV**
- One FQDN per line
- File path passed via CLI to the fetcher

Example:
```text
example.com
google.com
some-domain.net
````

---

## Output

### Fetch Stage

* One JSON file per FQDN in `./fetch/`
* Contains:

  * DNS results
  * HTTP fetch metadata
  * Redirect history
  * Content snippet
  * Optional TLS data
  * Block/WAF indicators

### Classify Stage

* One JSON file per FQDN in `./classify/`
* Contains:

  * Final canonical category
  * Raw LLM category (if used)
  * Confidence score
  * Rule or LLM decision metadata
  * Normalization details

---

## Installation

### Python

* Python **3.10+** recommended

### Required Python packages

```bash
pip install aiohttp httpx playwright tomli
```

(Optional, if using Playwright)

```bash
playwright install chromium
```

### curl-impersonate

Install separately if you want browser-accurate TLS/JA3 fallback:

* [https://github.com/lwthiker/curl-impersonate](https://github.com/lwthiker/curl-impersonate)

---

## vLLM Setup

### Hardware (example tested)

* NVIDIA RTX 5090 (32 GB VRAM)
* 96 GB system RAM

### vLLM Version

* `vllm==0.11.2`

### Model

* `Qwen/Qwen2.5-7B-Instruct`
* `bf16`
* `max_model_len = 2048`

### Start vLLM

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --dtype bf16 \
  --max-model-len 2048 \
  --host 127.0.0.1 \
  --port 8000
```

Verify:

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8000/v1/chat/completions
```

---

## Configuration

All configuration lives in **`wxawebcat.toml`**.

* Fetch tuning (DNS, HTTP, fallbacks)
* TLS collection
* LLM concurrency
* Rule engine fingerprints
* Category normalization mappings

CLI flags **always override** TOML values.

---

## Usage

### 1️⃣ Fetch stage

```bash
python wxawebcat_fetcher.py \
  --input domains.csv
```

Resume-safe:

* Existing JSON files in `./fetch/` are skipped automatically.

---

### 2️⃣ Classification stage

```bash
python wxawebcat.py
```

Resume-safe:

* Existing `.class.json` files in `./classify/` are skipped.

---

## Rule-Based Pre-Classification

Before sending anything to the LLM, the classifier applies fast deterministic rules:

* **Unreachable**

  * DNS NXDOMAIN / SERVFAIL
  * No A / AAAA / CNAME
  * Timeout / 52x errors
* **Blocked**

  * 403 / 429 + CAPTCHA / WAF fingerprints
* **Parked**

  * Domain-for-sale / parking providers
* **NonWebContent**

  * PDFs, images, binaries
* **Redirect gateways**

  * CDN or identity provider landing pages

These rules typically eliminate **60–90%** of LLM calls.

---

## Category Normalization

LLM output is normalized into a **canonical taxonomy**:

* Exact match
* Alias mapping
* Keyword rules
* Fallback default

Example:

```
LLM output: "e-commerce"
Canonical:  "Shopping"
```

Both **raw** and **canonical** categories are preserved in output for auditability.

---

## Performance Notes

* Fetch stage is **I/O bound**
* Classification stage is **GPU bound**
* Decoupling stages dramatically improves throughput
* Typical tuning knobs:

  * `fetch_concurrency`
  * `dns_concurrency`
  * `llm_concurrency`

---

## Known Edge Cases

* CDN / WAF protected sites (UPS, Lenovo, etc.)
* TLS fingerprinting discrepancies
* JavaScript-only pages
* Browser success ≠ programmatic success

Fallback order:

1. Playwright (most complete, slowest)
2. curl-impersonate (fast, accurate TLS)

---

## Roadmap / TODO

* [ ] Finalize classifier refinements
* [ ] Add fetch metrics summary report
* [ ] Optional DOM text snapshots for Playwright
* [ ] Stress test vLLM QPS and batching
* [ ] GitHub repo cleanup and examples
* [ ] Optional multi-item LLM batching

---

## License

Internal / private project.
License to be determined.

---

## Author

WHOISXMLAPI.COM (WHOIS API, Inc.) 2026
- or split into **README + docs/** structure
```
