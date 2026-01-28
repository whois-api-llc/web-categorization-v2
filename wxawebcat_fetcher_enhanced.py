#!/usr/bin/env python3
import argparse
import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import httpx

UTC = timezone.utc


def read_toml(path: str) -> dict:
    """Read TOML configuration file"""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    
    with open(path, "rb") as f:
        return tomllib.load(f)


# ----------------------------
# Config
# ----------------------------
@dataclass
class ClassifierConfig:
    fetch_dir: Path = Path("./fetch")
    out_dir: Path = Path("./classify")
    error_log: Path = Path("./classify_logs/errors.jsonl")
    hash_cache_file: Path = Path("./classify_logs/content_hash_cache.json")

    vllm_base_url: str = "http://127.0.0.1:8000/v1"
    model: str = "Qwen/Qwen2.5-7B-Instruct"

    llm_concurrency: int = 32
    file_concurrency: int = 200
    request_timeout_s: float = 60.0

    rule_confidence_cutoff: float = 0.85
    enable_content_hash_dedup: bool = True
    enable_tld_rules: bool = True
    min_content_length_for_hash: int = 50  # Don't hash very short content
    
    @classmethod
    def from_toml(cls, toml_path: str, fetch_dir: str = None, out_dir: str = None):
        """Create config from TOML file"""
        cfg_dict = read_toml(toml_path)
        
        # Get paths
        paths = cfg_dict.get("paths", {})
        
        # Get classifier config
        classifier_cfg = cfg_dict.get("classifier", {})
        
        # Get LLM config
        llm_cfg = cfg_dict.get("llm", {})
        
        # Get content hash config (new section)
        content_hash_cfg = cfg_dict.get("content_hash", {})
        
        # Get TLD config (new section)
        tld_cfg = cfg_dict.get("tld_rules", {})
        
        # Get logging config
        logging_cfg = cfg_dict.get("logging", {})
        
        return cls(
            fetch_dir=Path(fetch_dir or paths.get("fetch_dir", "./fetch")),
            out_dir=Path(out_dir or paths.get("classify_dir", "./classify")),
            error_log=Path(logging_cfg.get("error_log", "./logs/errors.jsonl")),
            hash_cache_file=Path(content_hash_cfg.get("cache_file", "./logs/content_hash_cache.json")),
            
            vllm_base_url=llm_cfg.get("base_url", "http://127.0.0.1:8000/v1"),
            model=llm_cfg.get("model", "Qwen/Qwen2.5-7B-Instruct"),
            
            llm_concurrency=llm_cfg.get("llm_concurrency", 32),
            file_concurrency=classifier_cfg.get("file_concurrency", 200),
            request_timeout_s=float(llm_cfg.get("request_timeout", 60)),
            
            rule_confidence_cutoff=float(classifier_cfg.get("rule_confidence_cutoff", 0.85)),
            enable_content_hash_dedup=content_hash_cfg.get("enabled", True),
            enable_tld_rules=tld_cfg.get("enabled", True),
            min_content_length_for_hash=content_hash_cfg.get("min_content_length", 50),
        )


# ----------------------------
# TLD Classification Mappings
# ----------------------------
TLD_CATEGORY_MAP = {
    # Government
    ".gov": ("Government", 0.99, "Government TLD"),
    ".gov.uk": ("Government", 0.99, "Government TLD"),
    ".gov.au": ("Government", 0.99, "Government TLD"),
    ".gov.ca": ("Government", 0.99, "Government TLD"),
    ".mil": ("Government", 0.99, "Military TLD"),
    
    # Education
    ".edu": ("Education", 0.98, "Educational institution TLD"),
    ".ac.uk": ("Education", 0.98, "Academic TLD"),
    ".edu.au": ("Education", 0.98, "Educational TLD"),
    ".edu.cn": ("Education", 0.98, "Educational TLD"),
    
    # Adult Content
    ".xxx": ("Adult", 0.99, "Adult content TLD"),
    ".adult": ("Adult", 0.98, "Adult content TLD"),
    ".porn": ("Adult", 0.99, "Adult content TLD"),
    ".sex": ("Adult", 0.98, "Adult content TLD"),
    
    # Cryptocurrency/Blockchain
    ".crypto": ("Technology", 0.85, "Cryptocurrency TLD"),
    ".nft": ("Technology", 0.85, "NFT/Blockchain TLD"),
    ".blockchain": ("Technology", 0.90, "Blockchain TLD"),
    
    # Geographic indicators (lower confidence)
    ".museum": ("Arts_Entertainment", 0.85, "Museum TLD"),
    ".church": ("Religion", 0.85, "Religious organization TLD"),
    ".bank": ("Finance", 0.90, "Banking TLD"),
    ".insurance": ("Finance", 0.85, "Insurance TLD"),
    
    # Development/Testing
    ".localhost": ("Development", 0.99, "Localhost TLD"),
    ".local": ("Development", 0.95, "Local development TLD"),
    ".test": ("Development", 0.99, "Test TLD"),
    ".example": ("Development", 0.99, "Example TLD"),
}


def extract_tld(fqdn: str) -> Optional[str]:
    """
    Extract TLD from FQDN, handling multi-part TLDs.
    Returns the TLD including the dot (e.g., '.gov', '.ac.uk')
    """
    if not fqdn:
        return None
    
    fqdn_lower = fqdn.lower().rstrip('.')
    
    # Check multi-part TLDs first (longest match)
    for tld in sorted(TLD_CATEGORY_MAP.keys(), key=len, reverse=True):
        if fqdn_lower.endswith(tld):
            return tld
    
    # Check single-part TLD
    if '.' in fqdn_lower:
        parts = fqdn_lower.split('.')
        tld = '.' + parts[-1]
        if tld in TLD_CATEGORY_MAP:
            return tld
    
    return None


def classify_by_tld(fqdn: str) -> Optional[Tuple[str, float, str]]:
    """
    Classify domain based purely on TLD.
    Returns (category, confidence, reason) or None.
    """
    tld = extract_tld(fqdn)
    if tld and tld in TLD_CATEGORY_MAP:
        category, confidence, reason = TLD_CATEGORY_MAP[tld]
        return (category, confidence, f"rule: TLD {tld} → {reason}")
    return None


# ----------------------------
# Content Hash Cache
# ----------------------------
class ContentHashCache:
    """
    Manages a cache of content hashes to their classifications.
    Saves ~30%+ LLM calls by detecting duplicate content (parked domains, etc.)
    """
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        self.load()
    
    def load(self):
        """Load cache from disk if it exists."""
        if self.cache_file.exists():
            try:
                with self.cache_file.open('r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"Loaded {len(self.cache)} cached content hashes from {self.cache_file}")
            except Exception as e:
                print(f"Warning: Could not load hash cache: {e}")
                self.cache = {}
    
    def save(self):
        """Persist cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_file.open('w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save hash cache: {e}")
    
    def compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached classification by content hash."""
        result = self.cache.get(content_hash)
        if result:
            self.hits += 1
        else:
            self.misses += 1
        return result
    
    def put(self, content_hash: str, classification: Dict[str, Any]):
        """Store classification in cache."""
        self.cache[content_hash] = classification
    
    def stats(self) -> Dict[str, int]:
        """Return cache statistics."""
        return {
            "cache_size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0.0
        }


def build_content_fingerprint(doc: Dict[str, Any]) -> Optional[str]:
    """
    Build a content fingerprint for deduplication.
    Combines normalized title + snippet + meta description.
    Returns None if content is too short/empty.
    """
    http = doc.get("http", {}) or {}
    title = norm_text(http.get("title") or "")
    snippet = norm_text(http.get("body_snippet") or "")
    meta_desc = norm_text(((http.get("meta", {}) or {}).get("description")) or "")
    
    # Combine all text fields
    combined = f"{title} {meta_desc} {snippet}".strip()
    
    # Don't hash very short content (likely varies too much)
    if len(combined) < 50:
        return None
    
    return combined


# ----------------------------
# Utils
# ----------------------------
def now_utc_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

def safe_read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def safe_write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def norm_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip().lower()


# ----------------------------
# Rule engine
# ----------------------------
PARKED_PATTERNS = [
    "domain for sale", "buy this domain", "this domain is for sale",
    "sedo", "afternic", "dan.com", "bodis", "parkingcrew",
    "is parked", "domain parked", "parked domain"
]

BLOCK_PATTERNS = [
    "access denied", "request blocked", "unusual traffic", "verify you are human",
    "captcha", "challenge", "checking your browser", "ddos protection",
    "attention required", "cloudflare", "akamai", "imperva", "incapsula"
]

NOTFOUND_PATTERNS = [
    "not found", "404", "page not found", "doesn't exist", "does not exist"
]

# Status code constants for better maintainability
UNREACHABLE_STATUS_CODES = {0, 408, 520, 521, 522, 523, 524}
BLOCKED_STATUS_CODES = {403, 429}
NOT_FOUND_STATUS_CODES = {404, 410}


def rule_preclass(doc: Dict[str, Any], enable_tld_rules: bool = True) -> Optional[Tuple[str, float, str]]:
    """
    Rule-based pre-classification.
    Returns (category, confidence, reason) or None if no rule matches.
    
    Order of checks:
    1. TLD-based classification (NEW - HIGH CONFIDENCE) - if enabled
    2. DNS unreachable
    3. HTTP unreachable
    4. Block/WAF detection
    5. Not found
    6. Parked domains
    7. Non-HTML content types
    """
    fqdn = doc.get("fqdn") or doc.get("domain") or ""

    # 🆕 TLD-based classification (ADDED) - only if enabled
    if enable_tld_rules:
        tld_result = classify_by_tld(fqdn)
        if tld_result:
            return tld_result

    dns = doc.get("dns", {}) or {}
    rcode = (dns.get("rcode") or "").upper()
    a = dns.get("a") or []
    aaaa = dns.get("aaaa") or []
    cname = dns.get("cname") or []

    http = doc.get("http", {}) or {}
    status = http.get("status")
    blocked = bool(http.get("blocked", False))
    content_type = norm_text(http.get("content_type") or http.get("headers", {}).get("content-type"))
    title = norm_text(http.get("title"))
    snippet = norm_text(http.get("body_snippet"))

    # DNS unreachable
    if rcode in {"NXDOMAIN", "SERVFAIL"}:
        return ("Unreachable", 0.99, f"rule: dns rcode={rcode}")
    if not a and not aaaa and not cname:
        return ("Unreachable", 0.95, "rule: no A/AAAA/CNAME")

    # HTTP unreachable
    if status in UNREACHABLE_STATUS_CODES:
        return ("Unreachable", 0.95, f"rule: http status={status}")

    # Block/WAF
    if blocked:
        return ("Blocked", 0.98, "rule: fetcher blocked=true")
    if status in BLOCKED_STATUS_CODES:
        combo = f"{title} {snippet}"
        if any(p in combo for p in BLOCK_PATTERNS):
            return ("Blocked", 0.95, f"rule: http {status} + block fingerprint")

    # Not found
    if status in NOT_FOUND_STATUS_CODES:
        combo = f"{title} {snippet}"
        if any(p in combo for p in NOTFOUND_PATTERNS):
            return ("Unreachable", 0.90, f"rule: http {status} + notfound fingerprint")

    # Parked
    combo = f"{title} {snippet}"
    if any(p in combo for p in PARKED_PATTERNS):
        return ("Parked", 0.95, "rule: parked/sale fingerprint")

    # Non-html buckets
    if content_type:
        if content_type.startswith("image/"):
            return ("NonWebContent", 0.90, f"rule: content-type={content_type}")
        if content_type.startswith("application/pdf"):
            return ("NonWebContent", 0.90, "rule: content-type=application/pdf")
        if any(content_type.startswith(x) for x in ["application/zip", "application/octet-stream"]):
            return ("NonWebContent", 0.85, f"rule: content-type={content_type}")

    return None


# ----------------------------
# vLLM client
# ----------------------------
def build_llm_payload(doc: Dict[str, Any], model: str) -> Dict[str, Any]:
    http = doc.get("http", {}) or {}
    dns = doc.get("dns", {}) or {}

    features = {
        "fqdn": doc.get("fqdn"),
        "final_url": http.get("final_url"),
        "status": http.get("status"),
        "content_type": http.get("content_type") or (http.get("headers", {}) or {}).get("content-type"),
        "title": http.get("title"),
        "meta_description": ((http.get("meta", {}) or {}).get("description")),
        "snippet": http.get("body_snippet"),
        "dns": {
            "rcode": dns.get("rcode"),
            "a": dns.get("a"),
            "aaaa": dns.get("aaaa"),
            "cname": dns.get("cname"),
            "mx": dns.get("mx"),
        },
        "blocked": http.get("blocked"),
        "block_reason": http.get("block_reason"),
        "fetch_method": http.get("fetch_method"),
    }

    system = (
        "You are a web categorization engine. "
        "You must classify the site into a high-level category suitable for URL/domain categorization. "
        "Return ONLY valid JSON, no markdown, no extra text."
    )

    user = (
        "Classify the following web fetch features. "
        "Return JSON with keys: category (string), confidence (0..1), labels (array of strings), rationale (short string). "
        "Categories should be broad (e.g., Business, Technology, Shopping, Finance, Education, News, Social, Adult, Gambling, "
        "Malware/Phishing, Parked, CDN/Edge, Unreachable, Other).\n\n"
        f"FEATURES:\n{json.dumps(features, ensure_ascii=False)}"
    )

    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 220,
    }

async def llm_classify(client: httpx.AsyncClient, cfg: ClassifierConfig, doc: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_llm_payload(doc, cfg.model)
    url = f"{cfg.vllm_base_url}/chat/completions"
    resp = await client.post(url, json=payload, timeout=cfg.request_timeout_s)
    resp.raise_for_status()
    data = resp.json()

    # vLLM OpenAI-compatible: choices[0].message.content
    content = data["choices"][0]["message"]["content"]
    # Try strict JSON parse. If it fails, wrap as error.
    try:
        parsed = json.loads(content)
        return {"ok": True, "parsed": parsed, "raw": data}
    except json.JSONDecodeError:
        return {"ok": False, "error": "llm_return_not_json", "content": content, "raw": data}


# ----------------------------
# Pipeline
# ----------------------------
@dataclass
class Metrics:
    total: int = 0
    skipped: int = 0
    rule: int = 0
    tld_classified: int = 0  # NEW
    hash_cache_hits: int = 0  # NEW
    llm: int = 0
    errors: int = 0
    blocked: int = 0
    unreachable: int = 0
    parked: int = 0

async def process_one(
    path: Path,
    cfg: ClassifierConfig,
    llm_sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    metrics: Metrics,
    hash_cache: ContentHashCache  # NEW
) -> None:
    out_path = cfg.out_dir / (path.stem + ".class.json")

    # Resume-safe skip
    if out_path.exists():
        metrics.skipped += 1
        return

    try:
        doc = await asyncio.to_thread(safe_read_json, path)
        fqdn = doc.get("fqdn") or path.stem

        # Rules first (includes TLD check if enabled)
        rule = rule_preclass(doc, enable_tld_rules=cfg.enable_tld_rules)
        if rule:
            category, conf, reason = rule
            metrics.rule += 1
            
            # Track TLD classifications specifically
            if "TLD" in reason:
                metrics.tld_classified += 1
            
            if category == "Blocked":
                metrics.blocked += 1
            elif category == "Unreachable":
                metrics.unreachable += 1
            elif category == "Parked":
                metrics.parked += 1

            result = {
                "fqdn": fqdn,
                "input_file": path.name,
                "ts_classify_utc": now_utc_iso(),
                "decision": {
                    "method": "rules",
                    "category": category,
                    "confidence": float(conf),
                    "reason": reason,
                },
                "signals": {
                    "http_status": (doc.get("http", {}) or {}).get("status"),
                    "content_type": (doc.get("http", {}) or {}).get("content_type"),
                    "blocked": (doc.get("http", {}) or {}).get("blocked"),
                    "final_url": (doc.get("http", {}) or {}).get("final_url"),
                    "title": (doc.get("http", {}) or {}).get("title"),
                },
                "llm": None,
            }
            await asyncio.to_thread(safe_write_json, out_path, result)
            return

        # 🆕 Content Hash Deduplication (ADDED)
        content_hash = None
        if cfg.enable_content_hash_dedup:
            content_fingerprint = build_content_fingerprint(doc)
            if content_fingerprint:
                content_hash = hash_cache.compute_hash(content_fingerprint)
                cached_result = hash_cache.get(content_hash)
                
                if cached_result:
                    # Cache hit! Reuse previous classification
                    metrics.hash_cache_hits += 1
                    result = {
                        "fqdn": fqdn,
                        "input_file": path.name,
                        "ts_classify_utc": now_utc_iso(),
                        "decision": {
                            "method": "hash_cache",
                            "category": cached_result["category"],
                            "confidence": cached_result["confidence"],
                            "reason": f"content hash match (similar to {cached_result.get('example_fqdn', 'previous domain')})",
                            "content_hash": content_hash[:16],  # Store partial hash for debugging
                        },
                        "signals": {
                            "http_status": (doc.get("http", {}) or {}).get("status"),
                            "content_type": (doc.get("http", {}) or {}).get("content_type"),
                            "blocked": (doc.get("http", {}) or {}).get("blocked"),
                            "final_url": (doc.get("http", {}) or {}).get("final_url"),
                            "title": (doc.get("http", {}) or {}).get("title"),
                        },
                        "llm": None,
                    }
                    await asyncio.to_thread(safe_write_json, out_path, result)
                    return

        # LLM path (cache miss or dedup disabled)
        async with llm_sem:
            llm_res = await llm_classify(client, cfg, doc)

        if not llm_res.get("ok"):
            metrics.errors += 1
            append_jsonl(cfg.error_log, {
                "ts_utc": now_utc_iso(),
                "fqdn": fqdn,
                "input_file": path.name,
                "error": llm_res.get("error"),
                "content": llm_res.get("content"),
            })
            result = {
                "fqdn": fqdn,
                "input_file": path.name,
                "ts_classify_utc": now_utc_iso(),
                "decision": {
                    "method": "error",
                    "category": "Other",
                    "confidence": 0.0,
                    "reason": "llm_return_not_json",
                },
                "signals": {
                    "http_status": (doc.get("http", {}) or {}).get("status"),
                    "content_type": (doc.get("http", {}) or {}).get("content_type"),
                    "blocked": (doc.get("http", {}) or {}).get("blocked"),
                    "final_url": (doc.get("http", {}) or {}).get("final_url"),
                    "title": (doc.get("http", {}) or {}).get("title"),
                },
                "llm": {
                    "model": cfg.model,
                    "raw": llm_res.get("raw"),
                },
            }
            await asyncio.to_thread(safe_write_json, out_path, result)
            return

        parsed = llm_res["parsed"]
        metrics.llm += 1

        # 🆕 Store in content hash cache (ADDED)
        if cfg.enable_content_hash_dedup and content_hash:
            hash_cache.put(content_hash, {
                "category": parsed.get("category", "Other"),
                "confidence": parsed.get("confidence", 0.5),
                "example_fqdn": fqdn,
                "cached_at": now_utc_iso(),
            })

        result = {
            "fqdn": fqdn,
            "input_file": path.name,
            "ts_classify_utc": now_utc_iso(),
            "decision": {
                "method": "llm",
                "category": parsed.get("category", "Other"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reason": parsed.get("rationale", ""),
                "labels": parsed.get("labels", []),
            },
            "signals": {
                "http_status": (doc.get("http", {}) or {}).get("status"),
                "content_type": (doc.get("http", {}) or {}).get("content_type"),
                "blocked": (doc.get("http", {}) or {}).get("blocked"),
                "final_url": (doc.get("http", {}) or {}).get("final_url"),
                "title": (doc.get("http", {}) or {}).get("title"),
            },
            "llm": {
                "model": cfg.model,
                "raw": llm_res.get("raw"),
            },
        }
        await asyncio.to_thread(safe_write_json, out_path, result)

    except Exception as e:
        metrics.errors += 1
        append_jsonl(cfg.error_log, {
            "ts_utc": now_utc_iso(),
            "fqdn": fqdn if 'fqdn' in locals() else path.stem,
            "input_file": path.name,
            "error": f"{type(e).__name__}: {e}",
        })


async def main_async(args: argparse.Namespace) -> int:
    # Load configuration from TOML if provided
    if args.config:
        cfg = ClassifierConfig.from_toml(
            args.config,
            fetch_dir=args.fetch_dir,
            out_dir=args.out_dir
        )
    else:
        cfg = ClassifierConfig(
            fetch_dir=Path(args.fetch_dir),
            out_dir=Path(args.out_dir),
        )
    
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    cfg.error_log.parent.mkdir(parents=True, exist_ok=True)

    # 🆕 Initialize content hash cache (ADDED)
    hash_cache = ContentHashCache(cfg.hash_cache_file)

    files = sorted(cfg.fetch_dir.glob("*.json"))
    total = len(files)
    if not total:
        print(f"No JSON files found in {cfg.fetch_dir}")
        return 1

    print(f"Found {total} files to classify")
    print(f"TLD rules: {'enabled' if cfg.enable_tld_rules else 'disabled'} ({len(TLD_CATEGORY_MAP)} TLDs)")
    print(f"Content hash deduplication: {'enabled' if cfg.enable_content_hash_dedup else 'disabled'}")
    print(f"LLM endpoint: {cfg.vllm_base_url}")
    print(f"LLM model: {cfg.model}")
    print(f"LLM concurrency: {cfg.llm_concurrency}")
    print(f"File concurrency: {cfg.file_concurrency}")
    print(f"Rule confidence cutoff: {cfg.rule_confidence_cutoff}")
    print()
    
    metrics = Metrics(total=total)
    llm_sem = asyncio.Semaphore(cfg.llm_concurrency)
    file_sem = asyncio.Semaphore(cfg.file_concurrency)

    timeout = httpx.Timeout(cfg.request_timeout_s)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def worker(p: Path):
            async with file_sem:
                await process_one(p, cfg, llm_sem, client, metrics, hash_cache)

        await asyncio.gather(*(worker(p) for p in files))

    # 🆕 Save hash cache (ADDED)
    hash_cache.save()

    # Enhanced summary with new metrics
    print("\n=== CLASSIFICATION SUMMARY ===")
    print(f"Total:                {metrics.total}")
    print(f"Skipped (resume):     {metrics.skipped}")
    print(f"Rule-based:           {metrics.rule}")
    print(f"  ├─ TLD classified:  {metrics.tld_classified}")  # NEW
    print(f"  ├─ Blocked:         {metrics.blocked}")
    print(f"  ├─ Unreachable:     {metrics.unreachable}")
    print(f"  └─ Parked:          {metrics.parked}")
    print(f"Hash cache hits:      {metrics.hash_cache_hits}")  # NEW
    print(f"LLM classified:       {metrics.llm}")
    print(f"Errors:               {metrics.errors}")
    
    # Hash cache statistics
    if cfg.enable_content_hash_dedup:
        cache_stats = hash_cache.stats()
        print(f"\n=== CONTENT HASH CACHE STATS ===")
        print(f"Cache size:           {cache_stats['cache_size']}")
        print(f"Hits:                 {cache_stats['hits']}")
        print(f"Misses:               {cache_stats['misses']}")
        print(f"Hit rate:             {cache_stats['hit_rate']:.1%}")
        
        # Calculate savings
        if metrics.llm > 0:
            total_llm_needed_without_cache = metrics.llm + metrics.hash_cache_hits
            savings_pct = (metrics.hash_cache_hits / total_llm_needed_without_cache) * 100
            print(f"LLM calls saved:      {metrics.hash_cache_hits} ({savings_pct:.1f}%)")

    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Web categorization classifier with TLD rules and content hash deduplication"
    )
    p.add_argument("--config", default=None, help="Path to TOML config file (optional)")
    p.add_argument("--fetch-dir", default="./fetch", help="Input directory with fetch JSON files")
    p.add_argument("--out-dir", default="./classify", help="Output directory for classifications")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
