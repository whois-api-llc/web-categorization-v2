#!/usr/bin/env python3
"""
wxawebcat_web_fetcher_simple.py - Ultra-simple fetcher by WXA (WHOIS API Inc)

"""

import argparse
import asyncio
import csv
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Optional
from collections import deque

import aiohttp
from aiohttp.resolver import AsyncResolver

from wxawebcat_db import get_connection, init_database


@dataclass
class FetchConfig:
    """Configuration"""
    workers: int = 50               # Concurrent workers
    rate_limit: float = 50.0        # Max requests per second
    http_timeout: float = 5.0       # Total timeout including DNS
    connect_timeout: float = 3.0    # Connection timeout
    db_path: str = "wxawebcat.db"
    dns_server: str = "165.232.131.164"  # Custom DNS server
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    max_body_bytes: int = 65536


class RateLimiter:
    """Token bucket rate limiter"""
    def __init__(self, rate: float):
        self.rate = rate  # tokens per second
        self.tokens = rate  # start full
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait until a token is available"""
        async with self.lock:
            now = time.time()
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return
            
            # Wait for token to become available
            wait_time = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)
            self.tokens = 0
            self.last_update = time.time()


@dataclass 
class Stats:
    """Statistics"""
    total: int = 0
    completed: int = 0
    success: int = 0
    failed: int = 0
    blocked: int = 0
    start_time: float = field(default_factory=time.time)
    error_counts: Dict[str, int] = field(default_factory=dict)
    
    def record_error(self, error_type: str):
        if error_type:
            # Simplify error names
            error_type = error_type.replace("ClientConnectorError", "connect")
            error_type = error_type.replace("ServerDisconnectedError", "disconnected")
            error_type = error_type.replace("ClientOSError", "os_error")
            error_type = error_type.replace("ClientResponseError", "bad_response")
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time
    
    @property
    def rate(self) -> float:
        return self.completed / self.elapsed if self.elapsed > 0 else 0
    
    def eta(self) -> str:
        if self.rate > 0:
            secs = (self.total - self.completed) / self.rate
            if secs < 60:
                return f"{secs:.0f}s"
            elif secs < 3600:
                return f"{secs/60:.1f}m"
            else:
                return f"{secs/3600:.1f}h"
        return "?"
    
    def top_errors(self, n: int = 5) -> str:
        if not self.error_counts:
            return "none"
        sorted_errors = sorted(self.error_counts.items(), key=lambda x: -x[1])[:n]
        return " | ".join(f"{k}:{v}" for k, v in sorted_errors)


def sanitize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    domain = re.sub(r'^https?://', '', domain)
    domain = domain.split('/')[0]
    domain = domain.split(':')[0]
    return domain


def extract_title(html: str) -> Optional[str]:
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1)
        title = re.sub(r'&[a-z]+;', ' ', title)
        return title.strip()[:500]
    return None


def extract_meta_description(html: str) -> Optional[str]:
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
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:max_chars]


async def fetch_domain(domain: str, session: aiohttp.ClientSession, 
                       cfg: FetchConfig) -> Dict:
    """
    Fetch a single domain. aiohttp handles DNS internally.
    """
    result = {
        "fqdn": domain,
        "dns": {"rcode": "NOERROR", "a": []},  # We won't have detailed DNS info
        "http": {"status": 0, "error": None, "title": None, "body_snippet": None, 
                 "meta": {}, "blocked": False, "content_type": None, "final_url": None},
        "status": "unknown"
    }
    
    timeout = aiohttp.ClientTimeout(
        total=cfg.http_timeout, 
        connect=cfg.connect_timeout,
        sock_connect=cfg.connect_timeout,
    )
    
    # Try HTTPS first, then HTTP
    for scheme in ["https", "http"]:
        url = f"{scheme}://{domain}"
        try:
            async with session.get(url, timeout=timeout, allow_redirects=True, 
                                   ssl=False) as resp:
                result["http"]["status"] = resp.status
                result["http"]["final_url"] = str(resp.url)
                result["http"]["content_type"] = resp.headers.get("content-type", "")
                
                # Check for blocking
                if resp.status in [403, 429]:
                    try:
                        text = await resp.text(encoding='utf-8', errors='ignore')
                        if any(kw in text.lower()[:2000] for kw in 
                               ["cloudflare", "captcha", "blocked", "access denied"]):
                            result["http"]["blocked"] = True
                            result["status"] = "blocked"
                            return result
                    except:
                        pass
                
                # Extract content if HTML
                if "text/html" in result["http"]["content_type"]:
                    try:
                        html = await resp.text(encoding='utf-8', errors='ignore')
                        html = html[:cfg.max_body_bytes]
                        result["http"]["title"] = extract_title(html)
                        meta = extract_meta_description(html)
                        if meta:
                            result["http"]["meta"]["description"] = meta
                        result["http"]["body_snippet"] = extract_visible_text(html)
                    except:
                        pass
                
                result["status"] = "success"
                return result
                
        except asyncio.TimeoutError:
            result["http"]["error"] = "timeout"
        except aiohttp.ClientConnectorError as e:
            # This includes DNS failures
            err_str = str(e).lower()
            if "getaddrinfo" in err_str or "name or service not known" in err_str:
                result["http"]["error"] = "dns_failed"
                result["dns"]["rcode"] = "NXDOMAIN"
            elif "connection refused" in err_str:
                result["http"]["error"] = "refused"
            else:
                result["http"]["error"] = "connect"
        except aiohttp.ServerDisconnectedError:
            result["http"]["error"] = "disconnected"
        except aiohttp.ClientError as e:
            result["http"]["error"] = type(e).__name__
        except Exception as e:
            result["http"]["error"] = type(e).__name__
    
    # If we get here, both HTTPS and HTTP failed
    if result["http"]["error"] == "dns_failed":
        result["status"] = "dns_failed"
    else:
        result["status"] = "http_failed"
    return result


def get_existing_domains(db_path: str) -> Set[str]:
    existing = set()
    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT fqdn FROM domains")
            for row in cursor:
                existing.add(row[0])
    except:
        pass
    return existing


def extract_domain_from_row(row: List[str]) -> str:
    if not row:
        return ""
    if len(row) >= 2 and row[0].strip().replace(',', '').isdigit():
        return sanitize_domain(row[1])
    return sanitize_domain(row[0])


def stream_domains(csv_path: str, skip: Set[str], limit: Optional[int] = None):
    count = 0
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if not row or not row[0].strip() or row[0].startswith('#'):
                continue
            if i == 0 and row[0].strip().lower() in ['rank', 'domain', 'fqdn']:
                continue
            domain = extract_domain_from_row(row)
            if domain and domain not in skip:
                yield domain
                count += 1
                if limit and count >= limit:
                    break


def batch_insert(conn, results: List[Dict]):
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany("""
        INSERT INTO domains (fqdn, dns_data, http_data, fetched_at, fetch_status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(fqdn) DO UPDATE SET
            dns_data = excluded.dns_data,
            http_data = excluded.http_data,
            fetched_at = excluded.fetched_at,
            fetch_status = excluded.fetch_status,
            updated_at = datetime('now')
    """, [(r["fqdn"], json.dumps(r["dns"]), json.dumps(r["http"]), 
           now, r["status"]) for r in results])


async def main_async(args):
    cfg = FetchConfig(
        workers=args.workers,
        rate_limit=args.rate,
        http_timeout=args.timeout,
        connect_timeout=min(args.timeout, 3.0),
        db_path=args.db,
        dns_server=args.dns_server,
    )
    
    init_database(cfg.db_path)
    
    print("Loading existing domains...")
    existing = get_existing_domains(cfg.db_path)
    print(f"Found {len(existing)} already fetched")
    
    print(f"Loading domains from {args.input}...")
    domains = list(stream_domains(args.input, existing, args.limit))
    total = len(domains)
    
    if total == 0:
        print("Nothing to fetch!")
        return
    
    print(f"\n{'='*70}")
    print(f"SIMPLE FETCHER (custom DNS: {cfg.dns_server})")
    print(f"{'='*70}")
    print(f"To fetch:         {total:,}")
    print(f"Workers:          {cfg.workers}")
    print(f"Rate limit:       {cfg.rate_limit}/s")
    print(f"Timeout:          {cfg.http_timeout}s")
    print(f"DNS server:       {cfg.dns_server}")
    print(f"Expected time:    {total / cfg.rate_limit / 3600:.1f} hours")
    print(f"{'='*70}\n")
    
    stats = Stats(total=total)
    rate_limiter = RateLimiter(cfg.rate_limit)
    
    # Results buffer for batch DB writes
    results_buffer = []
    buffer_lock = asyncio.Lock()
    
    # Work queue
    work_queue = asyncio.Queue()
    for domain in domains:
        await work_queue.put(domain)
    
    # Recent rate tracking
    recent_rates = deque(maxlen=10)
    last_completed = 0
    
    # Create aiohttp session with custom DNS resolver
    # This uses aiodns under the hood but aiohttp manages it
    resolver = AsyncResolver(nameservers=[cfg.dns_server])
    
    connector = aiohttp.TCPConnector(
        resolver=resolver,           # Use our custom DNS server
        limit=cfg.workers,           # Match worker count
        limit_per_host=3,            # Don't hammer single hosts
        ttl_dns_cache=300,           # Cache DNS for 5 minutes
        enable_cleanup_closed=True,
        force_close=False,
    )
    
    async def worker():
        """Worker: grab domain, fetch it, save result"""
        while True:
            try:
                domain = work_queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            
            # Rate limit before making request
            await rate_limiter.acquire()
            
            result = await fetch_domain(domain, session, cfg)
            
            # Update stats
            stats.completed += 1
            if result["status"] == "success":
                stats.success += 1
            elif result["status"] == "blocked":
                stats.blocked += 1
            else:
                stats.failed += 1
                stats.record_error(result["http"].get("error", "unknown"))
            
            # Buffer result
            async with buffer_lock:
                results_buffer.append(result)
            
            work_queue.task_done()
    
    async def db_writer():
        """Periodically flush results to database"""
        nonlocal results_buffer
        while stats.completed < stats.total:
            await asyncio.sleep(2.0)
            
            async with buffer_lock:
                if results_buffer:
                    to_write = results_buffer.copy()
                    results_buffer = []
                else:
                    to_write = []
            
            if to_write:
                with get_connection(cfg.db_path) as conn:
                    batch_insert(conn, to_write)
    
    async def reporter():
        """Report progress"""
        nonlocal last_completed
        while stats.completed < stats.total:
            await asyncio.sleep(2.0)
            
            delta = stats.completed - last_completed
            recent_rates.append(delta / 2.0)
            last_completed = stats.completed
            avg_rate = sum(recent_rates) / len(recent_rates) if recent_rates else 0
            
            pct = stats.completed / stats.total * 100
            success_pct = (stats.success / stats.completed * 100) if stats.completed > 0 else 0
            
            print(f"[{stats.completed:,}/{stats.total:,}] {pct:.1f}% | "
                  f"{avg_rate:.0f}/s | "
                  f"✓{stats.success} ({success_pct:.0f}%) ✗{stats.failed} 🛡{stats.blocked} | "
                  f"ETA: {stats.eta()}")
            
            if stats.failed > 0:
                print(f"  └─ Errors: {stats.top_errors()}")
    
    async with aiohttp.ClientSession(
        connector=connector,
        headers={"User-Agent": cfg.user_agent},
    ) as session:
        
        print(f"Starting {cfg.workers} workers...")
        
        # Start background tasks
        db_task = asyncio.create_task(db_writer())
        reporter_task = asyncio.create_task(reporter())
        
        # Start workers
        workers = [asyncio.create_task(worker()) for _ in range(cfg.workers)]
        
        # Wait for all work to complete
        await asyncio.gather(*workers)
        
        # Final DB flush
        if results_buffer:
            with get_connection(cfg.db_path) as conn:
                batch_insert(conn, results_buffer)
        
        # Cancel background tasks
        db_task.cancel()
        reporter_task.cancel()
    
    # Final stats
    success_pct = (stats.success / stats.completed * 100) if stats.completed > 0 else 0
    print(f"\n{'='*70}")
    print(f"COMPLETE")
    print(f"{'='*70}")
    print(f"Processed:    {stats.completed:,}")
    print(f"Success:      {stats.success:,} ({success_pct:.1f}%)")
    print(f"Failed:       {stats.failed:,}")
    print(f"Blocked:      {stats.blocked:,}")
    print(f"Time:         {stats.elapsed:.0f}s ({stats.elapsed/60:.1f}m)")
    print(f"Rate:         {stats.rate:.1f}/s")
    print(f"{'='*70}")
    if stats.error_counts:
        print(f"ERROR BREAKDOWN:")
        for err, count in sorted(stats.error_counts.items(), key=lambda x: -x[1]):
            pct = count / max(stats.failed, 1) * 100
            print(f"  {err:30s} {count:>8,} ({pct:.1f}%)")
    print(f"{'='*70}")


def parse_args():
    p = argparse.ArgumentParser(description="Simple fetcher with custom DNS")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--db", default="wxawebcat.db")
    p.add_argument("--limit", "-n", type=int)
    p.add_argument("--workers", "-w", type=int, default=50, 
                   help="Concurrent workers (default: 50)")
    p.add_argument("--rate", "-r", type=float, default=50.0,
                   help="Max requests per second (default: 50)")
    p.add_argument("--timeout", "-t", type=float, default=5.0,
                   help="Request timeout in seconds (default: 5)")
    p.add_argument("--dns-server", default="165.232.131.164",
                   help="DNS server to use (default: 165.232.131.164)")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))

# example: python3 wxawebcat_web_fetcher_simple.py   --input top1M.csv   --workers 20   --rate 15   --timeout 5

