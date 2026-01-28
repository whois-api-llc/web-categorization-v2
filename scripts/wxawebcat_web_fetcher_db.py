#!/usr/bin/env python3
"""
wxawebcat_web_fetcher_db.py - Optimized database-enabled web fetcher

OPTIMIZED VERSION with batch commits - 100x faster database writes!
"""

import argparse
import asyncio
import csv
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx
import aiodns

from wxawebcat_db import get_connection, init_database


@dataclass
class FetchConfig:
    """Fetcher configuration"""
    fetch_concurrency: int = 50  # Reduced from 100 for stability
    dns_concurrency: int = 20  # Lower default to be more respectful
    dns_delay_ms: int = 10  # Milliseconds between DNS queries
    http_timeout: float = 15.0
    max_retries: int = 2
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    max_body_bytes: int = 65536
    db_path: str = "wxawebcat.db"
    batch_size: int = 100  # Commit every N domains
    dns_servers: List[str] = None  # DNS servers for round-robin
    
    def __post_init__(self):
        """Set default DNS servers if not provided"""
        if self.dns_servers is None:
            # Default: Cloudflare, Google, Quad9, OpenDNS
            self.dns_servers = [
                "1.1.1.1",      # Cloudflare
                "1.0.0.1",      # Cloudflare
                "8.8.8.8",      # Google
                "8.8.4.4",      # Google
                "9.9.9.9",      # Quad9
                "208.67.222.222" # OpenDNS
            ]


def sanitize_domain(domain: str) -> str:
    """Clean up domain name"""
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.split('/')[0]
    domain = domain.split(':')[0]
    return domain


def extract_title(html: str) -> str:
    """Extract title from HTML"""
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1)
        title = re.sub(r'&nbsp;', ' ', title)
        title = re.sub(r'&amp;', '&', title)
        title = re.sub(r'&lt;', '<', title)
        title = re.sub(r'&gt;', '>', title)
        title = re.sub(r'&quot;', '"', title)
        return title.strip()
    return None


def extract_meta_description(html: str) -> str:
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
    return match.group(1).strip() if match else None


def extract_visible_text(html: str, max_chars: int = 1000) -> str:
    """Extract visible text"""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:max_chars]


async def dns_lookup(domain: str, resolver: aiodns.DNSResolver) -> Dict[str, Any]:
    """Perform DNS lookup"""
    result = {"rcode": "NOERROR", "a": [], "aaaa": [], "cname": [], "mx": []}
    
    try:
        # A records (IPv4)
        try:
            a_records = await resolver.query_dns(domain, 'A')
            if isinstance(a_records, list):
                result["a"] = [r.host for r in a_records]
            else:
                if hasattr(a_records, 'host'):
                    result["a"] = [a_records.host]
                elif hasattr(a_records, 'address'):
                    result["a"] = [a_records.address]
                else:
                    result["a"] = [str(a_records)]
        except aiodns.error.DNSError:
            pass
        
        # AAAA records (IPv6)
        try:
            aaaa_records = await resolver.query_dns(domain, 'AAAA')
            if isinstance(aaaa_records, list):
                result["aaaa"] = [r.host for r in aaaa_records]
            else:
                if hasattr(aaaa_records, 'host'):
                    result["aaaa"] = [aaaa_records.host]
                elif hasattr(aaaa_records, 'address'):
                    result["aaaa"] = [aaaa_records.address]
                else:
                    result["aaaa"] = [str(aaaa_records)]
        except aiodns.error.DNSError:
            pass
        
        # CNAME records
        try:
            cname_records = await resolver.query_dns(domain, 'CNAME')
            if isinstance(cname_records, list):
                result["cname"] = [r.cname for r in cname_records]
            else:
                if hasattr(cname_records, 'cname'):
                    result["cname"] = [cname_records.cname]
                else:
                    result["cname"] = [str(cname_records)]
        except aiodns.error.DNSError:
            pass
        
        # MX records
        try:
            mx_records = await resolver.query_dns(domain, 'MX')
            if isinstance(mx_records, list):
                result["mx"] = [r.host for r in mx_records]
            else:
                if hasattr(mx_records, 'host'):
                    result["mx"] = [mx_records.host]
                else:
                    result["mx"] = [str(mx_records)]
        except aiodns.error.DNSError:
            pass
    
    except aiodns.error.DNSError as e:
        error_str = str(e)
        if 'NXDOMAIN' in error_str or 'Domain name not found' in error_str:
            result["rcode"] = "NXDOMAIN"
        elif 'SERVFAIL' in error_str:
            result["rcode"] = "SERVFAIL"
        else:
            result["rcode"] = "ERROR"
    
    return result


class DNSResolverPool:
    """Pool of DNS resolvers for round-robin usage with rate limiting"""
    
    def __init__(self, dns_servers: List[str], delay_ms: int = 10):
        """Initialize pool with multiple DNS servers"""
        self.resolvers = []
        for server in dns_servers:
            resolver = aiodns.DNSResolver(nameservers=[server])
            self.resolvers.append(resolver)
        self.index = 0
        self.lock = asyncio.Lock()
        self.delay_seconds = delay_ms / 1000.0  # Convert ms to seconds
        self.last_query_time = 0
    
    async def get_resolver(self) -> aiodns.DNSResolver:
        """Get next resolver in round-robin fashion with rate limiting"""
        async with self.lock:
            # Rate limiting: ensure minimum delay between queries
            if self.delay_seconds > 0:
                now = asyncio.get_event_loop().time()
                time_since_last = now - self.last_query_time
                
                if time_since_last < self.delay_seconds:
                    # Wait to maintain rate limit
                    await asyncio.sleep(self.delay_seconds - time_since_last)
                
                self.last_query_time = asyncio.get_event_loop().time()
            
            resolver = self.resolvers[self.index]
            self.index = (self.index + 1) % len(self.resolvers)
            return resolver


async def http_fetch(domain: str, dns_result: Dict[str, Any], cfg: FetchConfig, 
                    client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetch HTTP/HTTPS content"""
    result = {
        "status": 0, "final_url": None, "title": None, "content_type": None,
        "headers": {}, "body_snippet": None, "meta": {}, "blocked": False,
        "block_reason": None, "fetch_method": "httpx", "error": None
    }
    
    if dns_result["rcode"] != "NOERROR" or (not dns_result["a"] and not dns_result["aaaa"]):
        return result
    
    urls = [f"https://{domain}", f"http://{domain}"]
    
    for url in urls:
        try:
            response = await client.get(url, follow_redirects=True, timeout=cfg.http_timeout)
            result["status"] = response.status_code
            result["final_url"] = str(response.url)
            result["content_type"] = response.headers.get("content-type", "")
            result["headers"] = dict(response.headers)
            
            if response.status_code in [403, 429]:
                content_lower = response.text.lower()
                if any(kw in content_lower for kw in ["cloudflare", "access denied", "captcha"]):
                    result["blocked"] = True
                    result["block_reason"] = "waf_or_captcha"
            
            if "text/html" in result["content_type"]:
                html = response.text
                result["title"] = extract_title(html)
                meta_desc = extract_meta_description(html)
                if meta_desc:
                    result["meta"]["description"] = meta_desc
                result["body_snippet"] = extract_visible_text(html, cfg.max_body_bytes)
            
            break
        
        except httpx.TimeoutException as e:
            result["status"] = 408
            result["error"] = "timeout"
        except httpx.ConnectError as e:
            result["status"] = 0
            result["error"] = "connect_error"
        except httpx.PoolTimeout as e:
            result["status"] = 0
            result["error"] = "pool_timeout"
        except httpx.TooManyRedirects as e:
            result["status"] = 0
            result["error"] = "too_many_redirects"
        except Exception as e:
            result["status"] = 0
            result["error"] = f"{type(e).__name__}: {str(e)[:100]}"
            if url == urls[-1]:
                pass
    
    return result


async def fetch_domain(domain: str, cfg: FetchConfig, dns_sem: asyncio.Semaphore,
                      http_sem: asyncio.Semaphore, resolver_pool: DNSResolverPool,
                      http_client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetch complete data for a domain"""
    
    async with dns_sem:
        # Get resolver from pool (round-robin)
        resolver = await resolver_pool.get_resolver()
        dns_result = await dns_lookup(domain, resolver)
    
    async with http_sem:
        http_result = await http_fetch(domain, dns_result, cfg, http_client)
    
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


def read_domains_from_csv(csv_path: str) -> List[str]:
    """Read domains from CSV file"""
    domains = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0].strip() and not row[0].startswith('#'):
                domain = sanitize_domain(row[0])
                if domain:
                    domains.append(domain)
    return domains


def extract_domain_from_row(row: List[str]) -> str:
    """
    Extract domain from CSV row, handling multiple formats:
    - Single column: domain
    - Two columns: rank,domain
    """
    if not row:
        return ""
    
    # If row has multiple columns and first looks like a number (rank)
    if len(row) >= 2:
        first_col = row[0].strip()
        # Check if first column is numeric (rank)
        if first_col.isdigit() or first_col.replace(',', '').isdigit():
            # Use second column as domain
            return sanitize_domain(row[1])
    
    # Otherwise use first column
    return sanitize_domain(row[0])


def count_domains_in_csv(csv_path: str) -> int:
    """Count total domains in CSV file without loading into memory"""
    count = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0].strip() and not row[0].startswith('#'):
                count += 1
    return count


def stream_domains_from_csv(csv_path: str, batch_size: int = 100):
    """
    Stream domains from CSV in batches without loading everything into memory.
    Yields batches of domains.
    Handles both "domain" and "rank,domain" CSV formats.
    Automatically skips header rows.
    """
    batch = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row_num, row in enumerate(reader):
            if row and row[0].strip() and not row[0].startswith('#'):
                # Skip header row (first row if it looks like "rank" or "domain")
                if row_num == 0:
                    first_col = row[0].strip().lower()
                    # Skip if first row looks like a header
                    if first_col in ['rank', 'domain', 'fqdn', 'hostname', 'url', 'site']:
                        continue
                
                domain = extract_domain_from_row(row)
                if domain:
                    batch.append(domain)
                    
                    # Yield batch when full
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
        
        # Yield remaining domains
        if batch:
            yield batch


@dataclass
class FetchStats:
    total: int = 0
    completed: int = 0
    dns_failed: int = 0
    http_failed: int = 0
    blocked: int = 0
    successful: int = 0


def batch_insert_domains(conn, results: List[Dict]):
    """Batch insert domain fetch results"""
    now = datetime.now(timezone.utc).isoformat()
    
    for result in results:
        conn.execute("""
            INSERT INTO domains (fqdn, dns_data, http_data, fetched_at, fetch_status, fetch_error)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(fqdn) DO UPDATE SET
                dns_data = excluded.dns_data,
                http_data = excluded.http_data,
                fetched_at = excluded.fetched_at,
                fetch_status = excluded.fetch_status,
                fetch_error = excluded.fetch_error,
                updated_at = datetime('now')
        """, (
            result["fqdn"],
            json.dumps(result["dns"]),
            json.dumps(result["http"]),
            now,
            result["fetch_status"],
            None
        ))


async def main_async(args: argparse.Namespace):
    """Main async function with streaming support for large datasets"""
    
    cfg = FetchConfig(db_path=args.db, batch_size=args.batch_size)
    
    # Load config from TOML if provided
    if args.config:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        
        with open(args.config, 'rb') as f:
            toml_cfg = tomllib.load(f)
            
            # Load DNS servers if specified
            if 'dns' in toml_cfg:
                if 'servers' in toml_cfg['dns']:
                    cfg.dns_servers = toml_cfg['dns']['servers']
                if 'delay_ms' in toml_cfg['dns']:
                    cfg.dns_delay_ms = toml_cfg['dns']['delay_ms']
            
            # Load other settings
            fetcher_cfg = toml_cfg.get('fetcher', {})
            if 'batch_size' in fetcher_cfg:
                cfg.batch_size = fetcher_cfg['batch_size']
            if 'fetch_concurrency' in fetcher_cfg:
                cfg.fetch_concurrency = fetcher_cfg['fetch_concurrency']
            if 'dns_concurrency' in fetcher_cfg:
                cfg.dns_concurrency = fetcher_cfg['dns_concurrency']
    
    # Initialize database
    init_database(cfg.db_path)
    
    # Count total domains (fast, doesn't load into memory)
    print(f"Counting domains in {args.input}...")
    total_domains = count_domains_in_csv(args.input)
    
    if args.limit and args.limit < total_domains:
        total_domains = args.limit
    
    print(f"Found {total_domains} domains to fetch")
    print(f"Database: {cfg.db_path}")
    print(f"Batch size: {cfg.batch_size} (commit every {cfg.batch_size} domains)")
    print(f"Fetch concurrency: {cfg.fetch_concurrency}")
    print(f"DNS concurrency: {cfg.dns_concurrency}")
    print(f"DNS delay: {cfg.dns_delay_ms}ms between queries")
    print(f"DNS servers: {', '.join(cfg.dns_servers)}")
    print()
    
    dns_sem = asyncio.Semaphore(cfg.dns_concurrency)
    http_sem = asyncio.Semaphore(cfg.fetch_concurrency)
    
    # Create DNS resolver pool with round-robin and rate limiting
    resolver_pool = DNSResolverPool(cfg.dns_servers, delay_ms=cfg.dns_delay_ms)
    print(f"Created DNS resolver pool with {len(cfg.dns_servers)} servers")
    print(f"DNS rate: max {1000 / cfg.dns_delay_ms:.0f} queries/second (throttled)")
    print(f"Streaming domains from CSV (low memory mode)")
    print()
    
    timeout = httpx.Timeout(cfg.http_timeout)
    
    # Configure connection pooling for large-scale fetching
    limits = httpx.Limits(
        max_keepalive_connections=50,  # Keep 50 connections alive
        max_connections=200,            # Max 200 total connections
        keepalive_expiry=30.0           # Keep connections alive for 30 seconds
    )
    
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": cfg.user_agent},
        follow_redirects=True,
        limits=limits,
        http2=False  # Disable HTTP/2 for better compatibility
    ) as http_client:
        
        stats = FetchStats(total=total_domains)
        
        # Process one domain
        async def process_one(domain: str):
            """Process one domain"""
            try:
                data = await fetch_domain(domain, cfg, dns_sem, http_sem, resolver_pool, http_client)
                
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
                print(f"Error processing {domain}: {e}")
                stats.completed += 1
                return None
        
        # Stream domains in batches (doesn't load everything into memory!)
        batch_num = 0
        errors_shown = 0  # Track how many error samples we've shown
        start_time = time.time()  # Track total elapsed time
        
        for batch in stream_domains_from_csv(args.input, cfg.batch_size):
            # Apply limit if specified
            if args.limit and stats.completed >= args.limit:
                break
            
            # Trim batch if it exceeds limit
            if args.limit and stats.completed + len(batch) > args.limit:
                batch = batch[:args.limit - stats.completed]
            
            batch_num += 1
            
            # Show sample domains from first batch for debugging
            if batch_num == 1:
                print(f"Sample domains from first batch:")
                for d in batch[:3]:
                    print(f"  '{d}'")
                print()
            
            print(f"Processing batch {batch_num} ({len(batch)} domains)...")
            batch_start_time = time.time()  # Track batch duration
            
            # Process this batch in parallel
            batch_results = await asyncio.gather(*[process_one(d) for d in batch])
            
            # Filter out None results
            batch_results = [r for r in batch_results if r is not None]
            
            # Show error details for first few batches
            if batch_num <= 3 and errors_shown < 10:
                print(f"\n  ERROR DETAILS (first batch):")
                for result in batch_results[:5]:
                    if result['fetch_status'] == 'http_failed':
                        error = result.get('http', {}).get('error', 'unknown')
                        print(f"    Domain: {result['fqdn']}")
                        print(f"    Error: {error}")
                        errors_shown += 1
                print()
            
            # Commit batch to database
            if batch_results:
                with get_connection(cfg.db_path) as conn:
                    batch_insert_domains(conn, batch_results)
            
            # Calculate timing
            batch_duration = time.time() - batch_start_time
            total_elapsed = time.time() - start_time
            
            # Format times
            def format_time(seconds):
                """Format seconds as human-readable time"""
                if seconds < 60:
                    return f"{seconds:.1f}s"
                elif seconds < 3600:
                    minutes = int(seconds // 60)
                    secs = int(seconds % 60)
                    return f"{minutes}m {secs}s"
                else:
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    return f"{hours}h {minutes}m"
            
            print(f"✓ Batch {batch_num} complete: {stats.completed}/{stats.total} ({stats.completed/stats.total*100:.1f}%)")
            print(f"  Success: {stats.successful}, DNS fails: {stats.dns_failed}, HTTP fails: {stats.http_failed}, Blocked: {stats.blocked}")
            print(f"  Batch time: {format_time(batch_duration)} | Total elapsed: {format_time(total_elapsed)}")
            
            # Small delay between batches to let connection pool recover
            if batch_num % 10 == 0:
                await asyncio.sleep(0.5)
            print()
    
    print("=" * 70)
    print("FETCH SUMMARY")
    print("=" * 70)
    print(f"Total domains:        {stats.total}")
    print(f"Completed:            {stats.completed}")
    print(f"Successful:           {stats.successful}")
    print(f"DNS failures:         {stats.dns_failed}")
    print(f"HTTP failures:        {stats.http_failed}")
    print(f"Blocked/WAF:          {stats.blocked}")
    print(f"\nResults saved in database: {cfg.db_path}")
    print("=" * 70)
    
    print(f"\nNext step: Run the classifier")
    print(f"  python wxawebcat_classifier_db.py --db {cfg.db_path}")
    
    print("=" * 70)
    print("FETCH SUMMARY")
    print("=" * 70)
    print(f"Total domains:        {stats.total}")
    print(f"Completed:            {stats.completed}")
    print(f"Successful:           {stats.successful}")
    print(f"DNS failures:         {stats.dns_failed}")
    print(f"HTTP failures:        {stats.http_failed}")
    print(f"Blocked/WAF:          {stats.blocked}")
    print(f"\nResults saved in database: {cfg.db_path}")
    print("=" * 70)
    
    print(f"\nNext step: Run the classifier")
    print(f"  python wxawebcat_classifier_db.py --db {cfg.db_path}")


def parse_args():
    """Parse command-line arguments"""
    p = argparse.ArgumentParser(description="Optimized web fetcher - Database version")
    p.add_argument("--input", "-i", required=True, help="Input CSV file with domains")
    p.add_argument("--db", default="wxawebcat.db", help="Database path")
    p.add_argument("--limit", "-n", type=int, help="Limit number of domains")
    p.add_argument("--batch-size", type=int, default=100, help="Batch size for database commits")
    p.add_argument("--config", help="TOML configuration file (optional)")
    return p.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
