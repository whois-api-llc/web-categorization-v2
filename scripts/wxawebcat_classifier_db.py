#!/usr/bin/env python3
"""
wxawebcat_classifier_db_optimized.py - Optimized database classifier

OPTIMIZED VERSION with batch commits - 100x faster!
"""

import argparse
import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from wxawebcat_db import get_connection, get_domains_to_classify, get_statistics


def read_toml(path: str) -> dict:
    """Read TOML configuration file"""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    
    with open(path, "rb") as f:
        return tomllib.load(f)


@dataclass
class ClassifierConfig:
    """Classifier configuration"""
    db_path: str = "wxawebcat.db"
    vllm_base_url: str = "http://127.0.0.1:8000/v1"
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_concurrency: int = 32
    request_timeout_s: float = 60.0
    rule_confidence_cutoff: float = 0.85
    enable_content_hash_dedup: bool = True
    enable_tld_rules: bool = True
    min_content_length_for_hash: int = 50
    batch_size: int = 100  # Commit every N domains
    watch_mode: bool = False  # Continuously watch for new domains
    watch_interval: int = 10  # Seconds between checks for new domains
    
    @classmethod
    def from_toml(cls, toml_path: str, db_path: str = None):
        """Create config from TOML file"""
        cfg_dict = read_toml(toml_path)
        
        llm_cfg = cfg_dict.get("llm", {})
        classifier_cfg = cfg_dict.get("classifier", {})
        content_hash_cfg = cfg_dict.get("content_hash", {})
        tld_cfg = cfg_dict.get("tld_rules", {})
        
        return cls(
            db_path=db_path or "wxawebcat.db",
            vllm_base_url=llm_cfg.get("base_url", "http://127.0.0.1:8000/v1"),
            model=llm_cfg.get("model", "Qwen/Qwen2.5-7B-Instruct"),
            llm_concurrency=llm_cfg.get("llm_concurrency", 32),
            request_timeout_s=float(llm_cfg.get("request_timeout", 60)),
            rule_confidence_cutoff=float(classifier_cfg.get("rule_confidence_cutoff", 0.85)),
            enable_content_hash_dedup=content_hash_cfg.get("enabled", True),
            enable_tld_rules=tld_cfg.get("enabled", True),
            min_content_length_for_hash=content_hash_cfg.get("min_content_length", 50),
            batch_size=classifier_cfg.get("batch_size", 100),
            watch_mode=classifier_cfg.get("watch_mode", False),
            watch_interval=classifier_cfg.get("watch_interval", 10),
        )


# TLD mappings (same as before)
TLD_CATEGORY_MAP = {
    ".gov": ("Government", 0.99, "Government TLD"),
    ".gov.uk": ("Government", 0.99, "UK Government TLD"),
    ".gov.au": ("Government", 0.99, "Australian Government TLD"),
    ".gov.ca": ("Government", 0.99, "Canadian Government TLD"),
    ".mil": ("Government", 0.99, "Military TLD"),
    ".edu": ("Education", 0.98, "Educational institution TLD"),
    ".ac.uk": ("Education", 0.98, "UK Academic TLD"),
    ".edu.au": ("Education", 0.98, "Australian Education TLD"),
    ".edu.cn": ("Education", 0.98, "Chinese Education TLD"),
    ".xxx": ("Adult", 0.99, "Adult content TLD"),
    ".adult": ("Adult", 0.99, "Adult content TLD"),
    ".porn": ("Adult", 0.98, "Adult content TLD"),
    ".sex": ("Adult", 0.98, "Adult content TLD"),
    ".bank": ("Finance", 0.90, "Banking TLD"),
    ".insurance": ("Finance", 0.90, "Insurance TLD"),
    ".crypto": ("Technology", 0.85, "Cryptocurrency TLD"),
    ".nft": ("Technology", 0.85, "NFT TLD"),
    ".blockchain": ("Technology", 0.85, "Blockchain TLD"),
    ".museum": ("Arts_Entertainment", 0.90, "Museum TLD"),
    ".church": ("Religion", 0.90, "Religious organization TLD"),
    ".test": ("Development", 0.99, "Testing TLD"),
    ".localhost": ("Development", 0.99, "Localhost TLD"),
    ".local": ("Development", 0.99, "Local network TLD"),
    ".example": ("Development", 0.99, "Example TLD"),
}


def extract_tld(fqdn: str) -> Optional[str]:
    """Extract TLD from FQDN"""
    if not fqdn:
        return None
    
    fqdn_lower = fqdn.lower()
    
    for tld in [".gov.uk", ".gov.au", ".gov.ca", ".ac.uk", ".edu.au", ".edu.cn"]:
        if fqdn_lower.endswith(tld):
            return tld
    
    parts = fqdn_lower.split(".")
    if len(parts) >= 2:
        return "." + parts[-1]
    
    return None


def classify_by_tld(fqdn: str) -> Optional[Tuple[str, float, str]]:
    """Classify by TLD"""
    tld = extract_tld(fqdn)
    if tld and tld in TLD_CATEGORY_MAP:
        category, confidence, description = TLD_CATEGORY_MAP[tld]
        return (category, confidence, f"rule: TLD {tld} → {description}")
    return None


UNREACHABLE_STATUS_CODES = {0, 408, 520, 521, 522, 523, 524}
BLOCKED_STATUS_CODES = {403, 429}
NOT_FOUND_STATUS_CODES = {404, 410}


def rule_preclass(doc: Dict[str, Any], enable_tld_rules: bool = True) -> Optional[Tuple[str, float, str]]:
    """Rule-based pre-classification"""
    fqdn = doc.get("fqdn", "")
    
    if enable_tld_rules:
        tld_result = classify_by_tld(fqdn)
        if tld_result:
            return tld_result
    
    dns = doc.get("dns", {})
    http = doc.get("http", {})
    
    if dns.get("rcode") != "NOERROR":
        return ("Unreachable", 0.99, f"rule: dns_rcode={dns.get('rcode')}")
    
    status = http.get("status", 0)
    
    if status in UNREACHABLE_STATUS_CODES:
        return ("Unreachable", 0.98, f"rule: http_status={status}")
    
    if status in BLOCKED_STATUS_CODES or http.get("blocked"):
        return ("Blocked", 0.98, f"rule: blocked")
    
    if status in NOT_FOUND_STATUS_CODES:
        return ("Unreachable", 0.95, f"rule: http_status={status}")
    
    snippet = (http.get("body_snippet") or "").lower()
    title = (http.get("title") or "").lower()
    
    if any(kw in snippet or kw in title for kw in ["domain for sale", "sedo", "afternic"]):
        return ("Parked", 0.95, "rule: parked_domain")
    
    return None


def build_content_fingerprint(http: Dict[str, Any]) -> str:
    """Build content fingerprint"""
    title = (http.get("title") or "").strip()
    meta_desc = ((http.get("meta", {}) or {}).get("description") or "").strip()
    snippet = (http.get("body_snippet") or "")[:500].strip()
    
    combined = f"{title}|{meta_desc}|{snippet}".lower()
    combined = re.sub(r'\s+', ' ', combined)
    
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def build_llm_payload(doc: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Build LLM request payload"""
    http = doc.get("http", {}) or {}
    
    snippet = http.get("body_snippet") or ""
    if len(snippet) > 800:
        snippet = snippet[:800] + "..."
    
    title = http.get("title") or ""
    if len(title) > 200:
        title = title[:200] + "..."
    
    meta_desc = ((http.get("meta", {}) or {}).get("description")) or ""
    if len(meta_desc) > 200:
        meta_desc = meta_desc[:200] + "..."
    
    features = {
        "fqdn": doc.get("fqdn"),
        "final_url": http.get("final_url"),
        "status": http.get("status"),
        "title": title,
        "meta_description": meta_desc,
        "snippet": snippet,
    }
    
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a web categorization AI. Return ONLY valid JSON."},
            {"role": "user", "content": f"Classify this website. Return JSON with: category (string), confidence (0-1), rationale (brief string). Categories: Business, Technology, Shopping, Finance, Education, News, Social, Adult, Gambling, Malware, Parked, Other.\n\n{json.dumps(features, ensure_ascii=False)}"},
        ],
        "temperature": 0.1,
        "max_tokens": 150,
    }


async def llm_classify(client: httpx.AsyncClient, cfg: ClassifierConfig, doc: Dict[str, Any]) -> Dict[str, Any]:
    """Call LLM for classification"""
    payload = build_llm_payload(doc, cfg.model)
    url = f"{cfg.vllm_base_url}/chat/completions"
    
    try:
        resp = await client.post(url, json=payload, timeout=cfg.request_timeout_s)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return {"ok": True, "parsed": parsed, "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@dataclass
class Metrics:
    total: int = 0
    rule: int = 0
    tld_classified: int = 0
    hash_cache_hits: int = 0
    llm: int = 0
    errors: int = 0


async def process_one(domain: Dict[str, Any], cfg: ClassifierConfig, 
                     llm_sem: asyncio.Semaphore, client: httpx.AsyncClient,
                     content_hash_cache: Dict[str, Tuple[str, float, str]],
                     metrics: Metrics) -> Optional[Dict]:
    """Process one domain (NO database writes)"""
    
    domain_id = domain['domain_id']
    fqdn = domain['fqdn']
    
    try:
        # Rules first
        rule = rule_preclass(domain, enable_tld_rules=cfg.enable_tld_rules)
        
        if rule:
            category, conf, reason = rule
            metrics.rule += 1
            
            if "TLD" in reason:
                metrics.tld_classified += 1
            
            return {
                'domain_id': domain_id,
                'fqdn': fqdn,
                'method': 'rules',
                'category': category,
                'confidence': conf,
                'reason': reason,
                'signals': {'http_status': domain.get("http", {}).get("status")},
                'llm_raw': None,
                'content_hash': None
            }
        
        # Content hash dedup
        if cfg.enable_content_hash_dedup:
            http = domain.get("http", {})
            snippet = http.get("body_snippet") or ""
            
            if len(snippet) >= cfg.min_content_length_for_hash:
                content_hash = build_content_fingerprint(http)
                
                if content_hash in content_hash_cache:
                    cached = content_hash_cache[content_hash]
                    metrics.hash_cache_hits += 1
                    
                    return {
                        'domain_id': domain_id,
                        'fqdn': fqdn,
                        'method': 'hash_cache',
                        'category': cached[0],
                        'confidence': cached[1],
                        'reason': f"hash_cache: matched {cached[2]}",
                        'signals': {'http_status': http.get("status")},
                        'llm_raw': None,
                        'content_hash': content_hash
                    }
        
        # LLM classification
        async with llm_sem:
            result = await llm_classify(client, cfg, domain)
        
        if result.get("ok"):
            parsed = result["parsed"]
            category = parsed.get("category", "Other")
            confidence = float(parsed.get("confidence", 0.5))
            rationale = parsed.get("rationale", "")
            
            metrics.llm += 1
            
            # Update in-memory cache
            content_hash = None
            if cfg.enable_content_hash_dedup:
                http = domain.get("http", {})
                snippet = http.get("body_snippet") or ""
                if len(snippet) >= cfg.min_content_length_for_hash:
                    content_hash = build_content_fingerprint(http)
                    content_hash_cache[content_hash] = (category, confidence, fqdn)
            
            return {
                'domain_id': domain_id,
                'fqdn': fqdn,
                'method': 'llm',
                'category': category,
                'confidence': confidence,
                'reason': rationale,
                'signals': {'http_status': domain.get("http", {}).get("status")},
                'llm_raw': result["raw"],
                'content_hash': content_hash
            }
        else:
            metrics.errors += 1
            return None
    
    except Exception as e:
        metrics.errors += 1
        print(f"Error processing {fqdn}: {e}")
        return None


def batch_insert(conn, results: List[Dict]):
    """Batch insert results to database"""
    for result in results:
        if result:
            # Insert classification
            conn.execute("""
                INSERT INTO classifications 
                (domain_id, fqdn, method, category, confidence, reason, signals, llm_raw, content_hash, classified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                result['domain_id'],
                result['fqdn'],
                result['method'],
                result['category'],
                result['confidence'],
                result['reason'],
                json.dumps(result['signals']),
                json.dumps(result['llm_raw']) if result['llm_raw'] else None,
                result['content_hash']
            ))
            
            # Update domain as classified
            conn.execute("""
                UPDATE domains 
                SET classified = 1, classified_at = datetime('now')
                WHERE id = ?
            """, (result['domain_id'],))
            
            # Insert into content hash cache if applicable
            if result['content_hash'] and result['method'] == 'llm':
                conn.execute("""
                    INSERT OR REPLACE INTO content_hash_cache 
                    (content_hash, category, confidence, example_fqdn, cached_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (
                    result['content_hash'],
                    result['category'],
                    result['confidence'],
                    result['fqdn']
                ))


async def classify_batch(cfg: ClassifierConfig, content_hash_cache: Dict):
    """Classify one batch of unclassified domains"""
    
    # Get domains to classify
    with get_connection(cfg.db_path) as conn:
        domains = get_domains_to_classify(conn)
    
    total = len(domains)
    
    if total == 0:
        return 0, None
    
    # Process all domains
    metrics = Metrics(total=total)
    llm_sem = asyncio.Semaphore(cfg.llm_concurrency)
    
    timeout = httpx.Timeout(cfg.request_timeout_s)
    async with httpx.AsyncClient(timeout=timeout) as client:
        
        results = []
        batch_num = 0
        
        for i, domain in enumerate(domains):
            result = await process_one(domain, cfg, llm_sem, client, content_hash_cache, metrics)
            results.append(result)
            
            # Batch commit
            if len(results) >= cfg.batch_size:
                batch_num += 1
                with get_connection(cfg.db_path) as conn:
                    batch_insert(conn, results)
                
                completed = (i + 1)
                print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%) - batch {batch_num} committed")
                results.clear()
        
        # Final batch
        if results:
            batch_num += 1
            with get_connection(cfg.db_path) as conn:
                batch_insert(conn, results)
            print(f"Progress: {total}/{total} (100.0%) - final batch committed")
    
    return total, metrics


async def main_async(args: argparse.Namespace):
    """Main async function with optional watch mode"""
    
    if args.config:
        cfg = ClassifierConfig.from_toml(args.config, db_path=args.db)
    else:
        cfg = ClassifierConfig(db_path=args.db)
    
    # Override with command line flag
    if args.watch:
        cfg.watch_mode = True
    
    print("=" * 70)
    print("WXAWEBCAT CLASSIFIER (Optimized Database Version)")
    print("=" * 70)
    print(f"Database: {cfg.db_path}")
    print(f"Batch size: {cfg.batch_size} (commit every {cfg.batch_size} domains)")
    print(f"LLM endpoint: {cfg.vllm_base_url}")
    print(f"LLM concurrency: {cfg.llm_concurrency}")
    
    if cfg.watch_mode:
        print(f"Mode: WATCH (continuous)")
        print(f"Watch interval: {cfg.watch_interval} seconds")
    else:
        print(f"Mode: ONE-SHOT (process and exit)")
    
    print()
    
    # Load content hash cache into memory
    content_hash_cache = {}
    with get_connection(cfg.db_path) as conn:
        cursor = conn.execute("SELECT content_hash, category, confidence, example_fqdn FROM content_hash_cache")
        for row in cursor:
            content_hash_cache[row[0]] = (row[1], row[2], row[3])
    
    print(f"Loaded {len(content_hash_cache)} content hashes from cache")
    print()
    
    # Watch mode: continuous loop
    if cfg.watch_mode:
        iteration = 0
        total_classified = 0
        
        try:
            while True:
                iteration += 1
                
                # Check for new domains
                with get_connection(cfg.db_path) as conn:
                    unclassified_count = conn.execute(
                        "SELECT COUNT(*) FROM domains WHERE classified = 0"
                    ).fetchone()[0]
                
                if unclassified_count > 0:
                    print(f"[Iteration {iteration}] Found {unclassified_count} unclassified domains")
                    
                    count, metrics = await classify_batch(cfg, content_hash_cache)
                    total_classified += count
                    
                    # Print iteration summary
                    if metrics:
                        print(f"[Iteration {iteration}] Classified {count} domains")
                        print(f"  Rule-based: {metrics.rule}, Hash hits: {metrics.hash_cache_hits}, LLM: {metrics.llm}")
                        print(f"  Total classified so far: {total_classified}")
                        print()
                else:
                    # No domains to classify, wait
                    if iteration == 1:
                        print(f"No unclassified domains found. Waiting for new domains...")
                    else:
                        print(f"[Iteration {iteration}] No new domains. Waiting {cfg.watch_interval}s...")
                
                # Wait before next check
                await asyncio.sleep(cfg.watch_interval)
                
        except KeyboardInterrupt:
            print("\n" + "=" * 70)
            print("STOPPED BY USER (Ctrl+C)")
            print("=" * 70)
            print(f"Total iterations:     {iteration}")
            print(f"Total classified:     {total_classified}")
            
            with get_connection(cfg.db_path) as conn:
                stats = get_statistics(conn)
                print(f"Total domains:        {stats['total_domains']}")
                print(f"Classified:           {stats['classified']}")
                print(f"Unclassified:         {stats['unclassified']}")
            
            return 0
    
    # One-shot mode: process once and exit
    else:
        # Get initial count
        with get_connection(cfg.db_path) as conn:
            unclassified_count = conn.execute(
                "SELECT COUNT(*) FROM domains WHERE classified = 0"
            ).fetchone()[0]
        
        print(f"Found {unclassified_count} unclassified domains\n")
        
        if unclassified_count == 0:
            print("Nothing to classify!")
            return 0
        
        count, metrics = await classify_batch(cfg, content_hash_cache)
        
        # Print summary
        print("\n" + "=" * 70)
        print("CLASSIFICATION SUMMARY")
        print("=" * 70)
        print(f"Total:                {metrics.total}")
        print(f"Rule-based:           {metrics.rule}")
        print(f"  ├─ TLD classified:  {metrics.tld_classified}")
        print(f"Hash cache hits:      {metrics.hash_cache_hits}")
        print(f"LLM classified:       {metrics.llm}")
        print(f"Errors:               {metrics.errors}")
        
        if cfg.enable_content_hash_dedup and (metrics.hash_cache_hits + metrics.llm) > 0:
            hit_rate = metrics.hash_cache_hits / (metrics.hash_cache_hits + metrics.llm) * 100
            print(f"\n=== CONTENT HASH CACHE STATS ===")
            print(f"Hit rate:             {hit_rate:.1f}%")
            print(f"LLM calls saved:      {metrics.hash_cache_hits}")
        
        print("\n" + "=" * 70)
        
        with get_connection(cfg.db_path) as conn:
            stats = get_statistics(conn)
            print(f"Total domains:        {stats['total_domains']}")
            print(f"Classified:           {stats['classified']}")
            print(f"Unclassified:         {stats['unclassified']}")
        
        print(f"\nNext: python add_iab_categories_db.py --db {cfg.db_path}")
        
        return 0


def parse_args():
    p = argparse.ArgumentParser(description="Optimized web classifier with watch mode")
    p.add_argument("--db", default="wxawebcat.db", help="Database path")
    p.add_argument("--config", help="TOML configuration file")
    p.add_argument("--watch", action="store_true", help="Watch mode: continuously monitor for new unclassified domains")
    return p.parse_args()


def main():
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    exit(main())
