#!/usr/bin/env python3
"""
wxawebcat_web_fetcher_db_fast.py - HIGH PERFORMANCE web fetcher

OPTIMIZED for speed:
- No artificial DNS delays (assumes local DNS cache)
- High concurrency (500+ parallel requests)
- Skips already-fetched domains
- Large connection pools
- Efficient batch processing
"""

import argparse
import asyncio
import csv
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

import httpx
import aiodns

from wxawebcat_db import get_connection, init_database


@dataclass
class FetchConfig:
    """Fetcher configuration - OPTIMIZED FOR SPEED"""
    # HIGH concurrency - adjust based on your server
    fetch_concurrency: int = 500      # Parallel HTTP requests
    dns_concurrency: int = 500        # Parallel DNS lookups
    
    # Timeouts - fail fast on unresponsive sites
    http_timeout: float = 10.0        # 10 seconds max per request
    dns_timeout: float = 5.0          # 5 seconds max for DNS
    
    # No artificial delays!
    max_retries: int = 1              # Single retry only
    
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    max_body_bytes: int = 65536
    db_path: str = "wxawebcat.db"
    batch_size: int = 500             # Larger batches = fewer DB commits
    
    # Connection pool - LARGE for high concurrency
    max_connections: int = 1000
    max_keepalive: int = 200
    
    # DNS - use local cache
    dns_server: str = "127.0.0.1"     # Local DNS cache


def sanitize_domain(domain: str) -> str:
    """Clean up domain name"""
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.split('/')[0]
    domain = domain.split(':')[0]
    return domain


def extract_title(html: str) -> Optional[str]:
    """Extract title from HTML"""
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1)
        title = re.sub(r'&nbsp;', ' ', title)
        title = re.sub(r'&amp;', '&', title)
        title = re.sub(r'&lt;', '<', title)
        title = re.sub(r'&gt;', '>', title)
        title = re.sub(r'&quot;', '"', title)
        return title.strip()[:500]  # Limit title length
    return None


def extract_meta_description(html: str) -> Optional[str]:
    """Extract meta description"""
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if not match:
        match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            html, re.IGNORECASE
        )
    return match.group(1).strip()[:1000] if match else None


def extract_visible_text(html: str, max_chars: int = 1000) -> str:
    """Extract visible text"""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:max_chars]


async def dns_lookup_fast(domain: str, resolver: aiodns.DNSResolver, 
                          timeout: float = 5.0) -> Dict[str, Any]:
    """Fast DNS lookup - only A records needed for HTTP fetch"""
    result = {"rcode": "NOERROR", "a": [], "aaaa": [], "cname": [], "mx": []}
    
    try:
        # Only fetch A records - that's all we need for HTTP
        a_records = await asyncio.wait_for(
            resolver.query_dns(domain, 'A'),
            timeout=timeout
        )
        result["a"] = [r.host for r in a_records]
    except asyncio.TimeoutError:
        result["rcode"] = "TIMEOUT"
    except aiodns.error.DNSError as e:
        error_str = str(e)
        if 'NXDOMAIN' in error_str or 'Domain name not found' in error_str:
            result["rcode"] = "NXDOMAIN"
        elif 'SERVFAIL' in error_str:
            result["rcode"] = "SERVFAIL"
        else:
            result["rcode"] = "ERROR"
    except Exception as e:
        result["rcode"] = "ERROR"
    
    return result


async def http_fetch_fast(domain: str, dns_result: Dict[str, Any], cfg: FetchConfig, 
                          client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fast HTTP fetch with early exit on errors"""
    result = {
        "status": 0, "final_url": None, "title": None, "content_type": None,
        "headers": {}, "body_snippet": None, "meta": {}, "blocked": False,
        "block_reason": None, "error": None
    }
    
    # Skip if no DNS
    if dns_result["rcode"] != "NOERROR" or not dns_result["a"]:
        return result
    
    # Try HTTPS first, then HTTP
    for scheme in ["https", "http"]:
        url = f"{scheme}://{domain}"
        try:
            response = await client.get(url)
            result["status"] = response.status_code
            result["final_url"] = str(response.url)
            result["content_type"] = response.headers.get("content-type", "")
            
            # Only store essential headers
            result["headers"] = {
                k: v for k, v in response.headers.items()
                if k.lower() in ('server', 'x-powered-by', 'content-type', 'location')
            }
            
            # Check for blocking
            if response.status_code in [403, 429]:
                content_lower = response.text[:2000].lower()
                if any(kw in content_lower for kw in ["cloudflare", "access denied", "captcha", "blocked"]):
                    result["blocked"] = True
                    result["block_reason"] = "waf_or_captcha"
            
            # Extract content if HTML
            if "text/html" in result["content_type"]:
                html = response.text[:cfg.max_body_bytes]
                result["title"] = extract_title(html)
                meta_desc = extract_meta_description(html)
                if meta_desc:
                    result["meta"]["description"] = meta_desc
                result["body_snippet"] = extract_visible_text(html, 1000)
            
            return result  # Success - exit early
            
        except httpx.TimeoutException:
            result["error"] = "timeout"
        except httpx.ConnectError:
            result["error"] = "connect_error"
        except httpx.TooManyRedirects:
            result["error"] = "too_many_redirects"
        except Exception as e:
            result["error"] = f"{type(e).__name__}"
    
    return result


async def fetch_domain_fast(domain: str, cfg: FetchConfig, 
                            dns_sem: asyncio.Semaphore,
                            http_sem: asyncio.Semaphore, 
                            resolver: aiodns.DNSResolver,
                            http_client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetch complete data for a domain - optimized"""
    
    # DNS lookup (with semaphore for concurrency control)
    async with dns_sem:
        dns_result = await dns_lookup_fast(domain, resolver, cfg.dns_timeout)
    
    # HTTP fetch (with semaphore for concurrency control)
    async with http_sem:
        http_result = await http_fetch_fast(domain, dns_result, cfg, http_client)
    
    # Determine fetch status
    if dns_result["rcode"] != "NOERROR":
        fetch_status = "dns_failed"
    elif http_result["status"] == 0:
        fetch_status = "http_failed"
    elif http_result["blocked"]:
        fetch_status = "blocked"
    else:
        fetch_status = "success"
    
    return {
        "fqdn": domain,
        "dns": dns_result,
        "http": http_result,
        "fetch_status": fetch_status
    }


def get_existing_domains(db_path: str) -> Set[str]:
    """Get set of already-fetched domains from database"""
    existing = set()
    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT fqdn FROM domains")
            for row in cursor:
                existing.add(row[0])
    except Exception as e:
        print(f"Warning: Could not read existing domains: {e}")
    return existing


def count_domains_in_csv(csv_path: str) -> int:
    """Count total domains in CSV file"""
    count = 0
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0].strip() and not row[0].startswith('#'):
                count += 1
    return count


def extract_domain_from_row(row: List[str]) -> str:
    """Extract domain from CSV row (handles rank,domain format)"""
    if not row:
        return ""
    
    if len(row) >= 2:
        first_col = row[0].strip()
        if first_col.isdigit() or first_col.replace(',', '').isdigit():
            return sanitize_domain(row[1])
    
    return sanitize_domain(row[0])


def stream_domains_from_csv(csv_path: str, skip_domains: Set[str], limit: Optional[int] = None):
    """
    Stream domains from CSV, skipping already-fetched ones.
    Yields individual domains (not batches) for maximum flexibility.
    """
    count = 0
    skipped = 0
    
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row_num, row in enumerate(reader):
            if not row or not row[0].strip() or row[0].startswith('#'):
                continue
            
            # Skip header
            if row_num == 0:
                first_col = row[0].strip().lower()
                if first_col in ['rank', 'domain', 'fqdn', 'hostname', 'url', 'site']:
                    continue
            
            domain = extract_domain_from_row(row)
            if not domain:
                continue
            
            # Skip if already in database
            if domain in skip_domains:
                skipped += 1
                continue
            
            yield domain
            count += 1
            
            if limit and count >= limit:
                break
    
    print(f"  Skipped {skipped} already-fetched domains")


@dataclass
class FetchStats:
    """Track fetch statistics"""
    total: int = 0
    completed: int = 0
    dns_failed: int = 0
    http_failed: int = 0
    blocked: int = 0
    successful: int = 0
    skipped: int = 0
    start_time: float = field(default_factory=time.time)
    
    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time
    
    @property
    def rate(self) -> float:
        if self.elapsed > 0:
            return self.completed / self.elapsed
        return 0
    
    @property
    def eta_seconds(self) -> float:
        if self.rate > 0:
            return (self.total - self.completed) / self.rate
        return 0
    
    def format_eta(self) -> str:
        secs = self.eta_seconds
        if secs < 60:
            return f"{secs:.0f}s"
        elif secs < 3600:
            return f"{secs/60:.1f}m"
        else:
            return f"{secs/3600:.1f}h"


def batch_insert_domains(conn, results: List[Dict]):
    """Batch insert domain fetch results"""
    now = datetime.now(timezone.utc).isoformat()
    
    conn.executemany("""
        INSERT INTO domains (fqdn, dns_data, http_data, fetched_at, fetch_status, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(fqdn) DO UPDATE SET
            dns_data = excluded.dns_data,
            http_data = excluded.http_data,
            fetched_at = excluded.fetched_at,
            fetch_status = excluded.fetch_status,
            fetch_error = excluded.fetch_error,
            updated_at = datetime('now')
    """, [
        (
            r["fqdn"],
            json.dumps(r["dns"]),
            json.dumps(r["http"]),
            now,
            r["fetch_status"],
            None
        )
        for r in results
    ])


async def main_async(args: argparse.Namespace):
    """Main async function - HIGH PERFORMANCE"""
    
    cfg = FetchConfig(
        db_path=args.db,
        batch_size=args.batch_size,
        fetch_concurrency=args.concurrency,
        dns_concurrency=args.concurrency,  # Match HTTP concurrency
        dns_server=args.dns_server,
        http_timeout=args.timeout,
        max_connections=args.concurrency * 2,  # 2x concurrency
    )
    
    # Initialize database
    init_database(cfg.db_path)
    
    # Get existing domains to skip
    print(f"Checking database for existing domains...")
    existing_domains = get_existing_domains(cfg.db_path)
    print(f"Found {len(existing_domains)} already-fetched domains to skip")
    
    # Count domains
    print(f"Counting domains in {args.input}...")
    total_in_file = count_domains_in_csv(args.input)
    
    # Calculate actual domains to fetch
    domains_to_fetch = []
    for domain in stream_domains_from_csv(args.input, existing_domains, args.limit):
        domains_to_fetch.append(domain)
    
    total_domains = len(domains_to_fetch)
    
    if total_domains == 0:
        print("\n✓ All domains already fetched! Nothing to do.")
        return
    
    print(f"\n{'='*70}")
    print(f"FETCH CONFIGURATION")
    print(f"{'='*70}")
    print(f"Domains in file:      {total_in_file}")
    print(f"Already fetched:      {len(existing_domains)}")
    print(f"To fetch:             {total_domains}")
    print(f"Concurrency:          {cfg.fetch_concurrency} parallel requests")
    print(f"HTTP timeout:         {cfg.http_timeout}s")
    print(f"DNS server:           {cfg.dns_server}")
    print(f"Batch size:           {cfg.batch_size}")
    print(f"Database:             {cfg.db_path}")
    print(f"{'='*70}\n")
    
    # Create semaphores for concurrency control
    dns_sem = asyncio.Semaphore(cfg.dns_concurrency)
    http_sem = asyncio.Semaphore(cfg.fetch_concurrency)
    
    # Create DNS resolver (using local cache)
    resolver = aiodns.DNSResolver(nameservers=[cfg.dns_server])
    
    # Configure HTTP client with large connection pool
    timeout = httpx.Timeout(cfg.http_timeout, connect=5.0)
    limits = httpx.Limits(
        max_keepalive_connections=cfg.max_keepalive,
        max_connections=cfg.max_connections,
        keepalive_expiry=30.0
    )
    
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": cfg.user_agent},
        follow_redirects=True,
        limits=limits,
        http2=False  # HTTP/1.1 is more reliable
    ) as http_client:
        
        stats = FetchStats(total=total_domains)
        results_buffer = []
        buffer_lock = asyncio.Lock()
        
        async def process_one(domain: str) -> Optional[Dict]:
            """Process one domain"""
            try:
                data = await fetch_domain_fast(
                    domain, cfg, dns_sem, http_sem, resolver, http_client
                )
                
                # Update stats
                if data["fetch_status"] == "dns_failed":
                    stats.dns_failed += 1
                elif data["fetch_status"] == "http_failed":
                    stats.http_failed += 1
                elif data["fetch_status"] == "blocked":
                    stats.blocked += 1
                else:
                    stats.successful += 1
                
                stats.completed += 1
                return data
                
            except Exception as e:
                stats.completed += 1
                stats.http_failed += 1
                return {
                    "fqdn": domain,
                    "dns": {"rcode": "ERROR", "a": [], "aaaa": [], "cname": [], "mx": []},
                    "http": {"status": 0, "error": str(e)},
                    "fetch_status": "http_failed"
                }
        
        async def worker(queue: asyncio.Queue):
            """Worker that continuously processes domains from queue"""
            while True:
                try:
                    domain = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Check if we should exit (queue empty and no more domains)
                    if queue.empty():
                        return
                    continue
                
                if domain is None:  # Poison pill - shutdown signal
                    return
                
                result = await process_one(domain)
                
                if result:
                    async with buffer_lock:
                        results_buffer.append(result)
                
                queue.task_done()
        
        async def db_writer():
            """Periodically flush results to database"""
            while True:
                await asyncio.sleep(2.0)  # Flush every 2 seconds
                
                async with buffer_lock:
                    if results_buffer:
                        to_write = results_buffer.copy()
                        results_buffer.clear()
                    else:
                        to_write = []
                
                if to_write:
                    with get_connection(cfg.db_path) as conn:
                        batch_insert_domains(conn, to_write)
        
        async def progress_reporter():
            """Report progress periodically"""
            last_completed = 0
            while stats.completed < stats.total:
                await asyncio.sleep(3.0)  # Report every 3 seconds
                
                current = stats.completed
                recent_rate = (current - last_completed) / 3.0  # Rate over last 3 seconds
                last_completed = current
                
                pct = stats.completed / stats.total * 100
                print(f"[{stats.completed:,}/{stats.total:,}] {pct:.1f}% | "
                      f"{stats.rate:.1f}/s (recent: {recent_rate:.0f}/s) | ETA: {stats.format_eta()} | "
                      f"✓{stats.successful} ✗DNS:{stats.dns_failed} ✗HTTP:{stats.http_failed} 🛡{stats.blocked}")
        
        # Create work queue
        queue = asyncio.Queue(maxsize=cfg.fetch_concurrency * 2)
        
        # Start workers
        num_workers = cfg.fetch_concurrency
        workers = [asyncio.create_task(worker(queue)) for _ in range(num_workers)]
        
        # Start DB writer and progress reporter
        db_task = asyncio.create_task(db_writer())
        progress_task = asyncio.create_task(progress_reporter())
        
        print(f"Started {num_workers} workers...")
        
        # Feed domains to queue
        for domain in domains_to_fetch:
            await queue.put(domain)
        
        # Wait for all work to complete
        await queue.join()
        
        # Send shutdown signal to workers
        for _ in range(num_workers):
            await queue.put(None)
        
        # Wait for workers to finish
        await asyncio.gather(*workers)
        
        # Cancel background tasks
        db_task.cancel()
        progress_task.cancel()
        
        # Final flush of any remaining results
        if results_buffer:
            with get_connection(cfg.db_path) as conn:
                batch_insert_domains(conn, results_buffer)
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"FETCH COMPLETE")
    print(f"{'='*70}")
    print(f"Total fetched:        {stats.completed:,}")
    print(f"Successful:           {stats.successful:,} ({stats.successful/stats.completed*100:.1f}%)")
    print(f"DNS failures:         {stats.dns_failed:,}")
    print(f"HTTP failures:        {stats.http_failed:,}")
    print(f"Blocked/WAF:          {stats.blocked:,}")
    print(f"Time elapsed:         {stats.elapsed:.1f}s ({stats.elapsed/60:.1f}m)")
    print(f"Average rate:         {stats.rate:.1f} domains/second")
    print(f"Database:             {cfg.db_path}")
    print(f"{'='*70}")


def load_toml_config(config_path: str) -> dict:
    """Load configuration from TOML file"""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("Warning: tomllib/tomli not available, cannot load TOML config")
            return {}
    
    with open(config_path, 'rb') as f:
        return tomllib.load(f)


def parse_args():
    """Parse command-line arguments"""
    p = argparse.ArgumentParser(
        description="HIGH PERFORMANCE web fetcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    p.add_argument("--input", "-i", required=True, help="Input CSV file with domains")
    p.add_argument("--db", default="wxawebcat.db", help="Database path")
    p.add_argument("--limit", "-n", type=int, help="Limit number of domains to fetch")
    p.add_argument("--batch-size", type=int, default=None, help="Batch size for DB commits")
    p.add_argument("--concurrency", "-c", type=int, default=None, 
                   help="Number of parallel requests")
    p.add_argument("--dns-server", default=None, 
                   help="DNS server (use local cache)")
    p.add_argument("--timeout", "-t", type=float, default=None,
                   help="HTTP timeout in seconds")
    p.add_argument("--config", help="TOML configuration file (optional)")
    
    args = p.parse_args()
    
    # Load TOML config if provided
    if args.config:
        print(f"Loading config from {args.config}...")
        toml_cfg = load_toml_config(args.config)
        
        # Extract settings from TOML (CLI args override TOML)
        fetcher_cfg = toml_cfg.get('fetcher', {})
        dns_cfg = toml_cfg.get('dns', {})
        
        # Apply TOML values if CLI args not specified
        if args.batch_size is None:
            args.batch_size = fetcher_cfg.get('batch_size', 500)
        if args.concurrency is None:
            args.concurrency = fetcher_cfg.get('fetch_concurrency', 
                              fetcher_cfg.get('concurrency', 500))
        if args.timeout is None:
            args.timeout = fetcher_cfg.get('http_timeout', 
                          fetcher_cfg.get('timeout', 10.0))
        if args.dns_server is None:
            # Check for dns.server or dns.servers[0]
            if 'server' in dns_cfg:
                args.dns_server = dns_cfg['server']
            elif 'servers' in dns_cfg and dns_cfg['servers']:
                args.dns_server = dns_cfg['servers'][0]
            else:
                args.dns_server = "127.0.0.1"
    
    # Set defaults for any still-None values
    if args.batch_size is None:
        args.batch_size = 500
    if args.concurrency is None:
        args.concurrency = 500
    if args.timeout is None:
        args.timeout = 10.0
    if args.dns_server is None:
        args.dns_server = "127.0.0.1"
    
    return args


def main():
    """Main entry point"""
    args = parse_args()
    
    print(f"\n🚀 HIGH PERFORMANCE WEB FETCHER")
    print(f"   Concurrency: {args.concurrency} parallel requests")
    print(f"   No artificial delays!")
    print()
    
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
