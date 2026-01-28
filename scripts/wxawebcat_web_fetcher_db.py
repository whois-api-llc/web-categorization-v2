#!/usr/bin/env python3
"""
wxawebcat_web_fetcher_pipeline.py - PIPELINE-BASED high performance fetcher

Architecture:
- DNS workers: resolve domains → push to http_queue
- HTTP workers: fetch pages from resolved domains → push to results_queue  
- DB writer: batch writes results

DNS and HTTP are completely decoupled - slow HTTP doesn't block DNS!
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

import httpx
import aiodns

from wxawebcat_db import get_connection, init_database


@dataclass
class PipelineConfig:
    """Pipeline configuration"""
    dns_workers: int = 100          # DNS resolution workers
    http_workers: int = 500         # HTTP fetch workers
    http_timeout: float = 1.5       # Very aggressive timeout
    dns_timeout: float = 2.0        # Fast DNS timeout
    max_connections: int = 2000     # Large connection pool
    keepalive_expiry: float = 5.0   # Short keepalive
    db_path: str = "wxawebcat.db"
    dns_server: str = "165.232.131.164"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    max_body_bytes: int = 65536


@dataclass 
class PipelineStats:
    """Track pipeline statistics"""
    total: int = 0
    dns_completed: int = 0
    dns_success: int = 0
    dns_failed: int = 0
    http_completed: int = 0
    http_success: int = 0
    http_failed: int = 0
    http_blocked: int = 0
    db_written: int = 0
    start_time: float = field(default_factory=time.time)
    
    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time
    
    @property
    def dns_rate(self) -> float:
        return self.dns_completed / self.elapsed if self.elapsed > 0 else 0
    
    @property
    def http_rate(self) -> float:
        return self.http_completed / self.elapsed if self.elapsed > 0 else 0
    
    @property
    def completed(self) -> int:
        return self.http_completed + self.dns_failed  # HTTP done + DNS failures (no HTTP needed)
    
    @property
    def overall_rate(self) -> float:
        return self.completed / self.elapsed if self.elapsed > 0 else 0
    
    def eta_seconds(self) -> float:
        rate = self.overall_rate
        if rate > 0:
            return (self.total - self.completed) / rate
        return 0
    
    def format_eta(self) -> str:
        secs = self.eta_seconds()
        if secs < 60:
            return f"{secs:.0f}s"
        elif secs < 3600:
            return f"{secs/60:.1f}m"
        else:
            return f"{secs/3600:.1f}h"


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
        title = re.sub(r'&nbsp;', ' ', title)
        title = re.sub(r'&amp;', '&', title)
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


async def dns_resolve(domain: str, resolver: aiodns.DNSResolver, 
                      timeout: float) -> Dict[str, Any]:
    """Fast DNS resolution"""
    result = {"rcode": "NOERROR", "a": []}
    
    try:
        response = await asyncio.wait_for(
            resolver.query_dns(domain, 'A'),
            timeout=timeout
        )
        
        ips = []
        if hasattr(response, 'answer'):
            for record in response.answer:
                if hasattr(record, 'data') and hasattr(record.data, 'addr'):
                    ips.append(record.data.addr)
        elif isinstance(response, list):
            for r in response:
                if hasattr(r, 'host'):
                    ips.append(r.host)
        
        result["a"] = ips
        
    except asyncio.TimeoutError:
        result["rcode"] = "TIMEOUT"
    except aiodns.error.DNSError as e:
        error_str = str(e)
        if 'NXDOMAIN' in error_str:
            result["rcode"] = "NXDOMAIN"
        elif 'SERVFAIL' in error_str or 'general failure' in error_str:
            result["rcode"] = "SERVFAIL"
        else:
            result["rcode"] = "ERROR"
    except Exception:
        result["rcode"] = "ERROR"
    
    return result


async def http_fetch(domain: str, ips: List[str], cfg: PipelineConfig,
                     client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fast HTTP fetch"""
    result = {
        "status": 0, "final_url": None, "title": None, "content_type": None,
        "headers": {}, "body_snippet": None, "meta": {}, "blocked": False,
        "error": None
    }
    
    if not ips:
        return result
    
    for scheme in ["https", "http"]:
        url = f"{scheme}://{domain}"
        try:
            response = await client.get(url)
            result["status"] = response.status_code
            result["final_url"] = str(response.url)
            result["content_type"] = response.headers.get("content-type", "")
            
            if response.status_code in [403, 429]:
                content_lower = response.text[:2000].lower()
                if any(kw in content_lower for kw in ["cloudflare", "captcha", "blocked"]):
                    result["blocked"] = True
            
            if "text/html" in result["content_type"]:
                html = response.text[:cfg.max_body_bytes]
                result["title"] = extract_title(html)
                meta_desc = extract_meta_description(html)
                if meta_desc:
                    result["meta"]["description"] = meta_desc
                result["body_snippet"] = extract_visible_text(html, 1000)
            
            return result
            
        except httpx.TimeoutException:
            result["error"] = "timeout"
        except httpx.ConnectError:
            result["error"] = "connect_error"
        except Exception as e:
            result["error"] = type(e).__name__
    
    return result


def get_existing_domains(db_path: str) -> Set[str]:
    existing = set()
    try:
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT fqdn FROM domains")
            for row in cursor:
                existing.add(row[0])
    except Exception:
        pass
    return existing


def extract_domain_from_row(row: List[str]) -> str:
    if not row:
        return ""
    if len(row) >= 2:
        first_col = row[0].strip()
        if first_col.isdigit() or first_col.replace(',', '').isdigit():
            return sanitize_domain(row[1])
    return sanitize_domain(row[0])


def stream_domains(csv_path: str, skip_domains: Set[str], limit: Optional[int] = None):
    """Stream domains from CSV, skipping existing"""
    count = 0
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row_num, row in enumerate(reader):
            if not row or not row[0].strip() or row[0].startswith('#'):
                continue
            if row_num == 0:
                first_col = row[0].strip().lower()
                if first_col in ['rank', 'domain', 'fqdn', 'hostname', 'url', 'site']:
                    continue
            
            domain = extract_domain_from_row(row)
            if domain and domain not in skip_domains:
                yield domain
                count += 1
                if limit and count >= limit:
                    break


def batch_insert_domains(conn, results: List[Dict]):
    """Batch insert results"""
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany("""
        INSERT INTO domains (fqdn, dns_data, http_data, fetched_at, fetch_status, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(fqdn) DO UPDATE SET
            dns_data = excluded.dns_data,
            http_data = excluded.http_data,
            fetched_at = excluded.fetched_at,
            fetch_status = excluded.fetch_status,
            updated_at = datetime('now')
    """, [
        (r["fqdn"], json.dumps(r["dns"]), json.dumps(r["http"]), now, r["fetch_status"], None)
        for r in results
    ])


async def main_async(args: argparse.Namespace):
    """Pipeline-based fetcher"""
    
    cfg = PipelineConfig(
        dns_workers=args.dns_workers,
        http_workers=args.http_workers,
        http_timeout=args.timeout,
        dns_timeout=args.timeout,
        db_path=args.db,
        dns_server=args.dns_server,
    )
    
    # Initialize
    init_database(cfg.db_path)
    
    print(f"Loading existing domains from database...")
    existing = get_existing_domains(cfg.db_path)
    print(f"Found {len(existing)} already-fetched domains")
    
    print(f"Loading domains from {args.input}...")
    domains = list(stream_domains(args.input, existing, args.limit))
    total = len(domains)
    
    if total == 0:
        print("All domains already fetched!")
        return
    
    print(f"\n{'='*70}")
    print(f"PIPELINE CONFIGURATION")
    print(f"{'='*70}")
    print(f"Domains to fetch:     {total:,}")
    print(f"DNS workers:          {cfg.dns_workers}")
    print(f"HTTP workers:         {cfg.http_workers}")
    print(f"Timeout:              {cfg.http_timeout}s")
    print(f"DNS server:           {cfg.dns_server}")
    print(f"{'='*70}\n")
    
    # Queues for pipeline
    dns_queue = asyncio.Queue()           # Domains waiting for DNS
    http_queue = asyncio.Queue()          # Resolved domains waiting for HTTP
    results_queue = asyncio.Queue()       # Results waiting for DB write
    
    stats = PipelineStats(total=total)
    resolver = aiodns.DNSResolver(nameservers=[cfg.dns_server])
    
    # Track recent rates
    recent_dns = deque(maxlen=10)
    recent_http = deque(maxlen=10)
    last_dns_count = 0
    last_http_count = 0
    
    # DNS Workers
    async def dns_worker():
        while True:
            try:
                domain = await asyncio.wait_for(dns_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if dns_queue.empty():
                    return
                continue
            
            if domain is None:
                return
            
            dns_result = await dns_resolve(domain, resolver, cfg.dns_timeout)
            stats.dns_completed += 1
            
            if dns_result["rcode"] == "NOERROR" and dns_result["a"]:
                stats.dns_success += 1
                # Push to HTTP queue
                await http_queue.put((domain, dns_result))
            else:
                stats.dns_failed += 1
                # No HTTP needed - write DNS failure directly
                await results_queue.put({
                    "fqdn": domain,
                    "dns": dns_result,
                    "http": {"status": 0},
                    "fetch_status": "dns_failed"
                })
            
            dns_queue.task_done()
    
    # HTTP Workers
    async def http_worker(client: httpx.AsyncClient):
        while True:
            try:
                item = await asyncio.wait_for(http_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Check if DNS is done and queue is empty
                if dns_queue.empty() and http_queue.empty():
                    return
                continue
            
            if item is None:
                return
            
            domain, dns_result = item
            http_result = await http_fetch(domain, dns_result["a"], cfg, client)
            stats.http_completed += 1
            
            if http_result["status"] == 0:
                stats.http_failed += 1
                fetch_status = "http_failed"
            elif http_result["blocked"]:
                stats.http_blocked += 1
                fetch_status = "blocked"
            else:
                stats.http_success += 1
                fetch_status = "success"
            
            await results_queue.put({
                "fqdn": domain,
                "dns": dns_result,
                "http": http_result,
                "fetch_status": fetch_status
            })
            
            http_queue.task_done()
    
    # DB Writer
    async def db_writer():
        buffer = []
        last_write = time.time()
        
        while True:
            try:
                result = await asyncio.wait_for(results_queue.get(), timeout=0.5)
                buffer.append(result)
                results_queue.task_done()
            except asyncio.TimeoutError:
                pass
            
            # Write every 2 seconds or every 500 results
            if buffer and (len(buffer) >= 500 or time.time() - last_write > 2.0):
                with get_connection(cfg.db_path) as conn:
                    batch_insert_domains(conn, buffer)
                stats.db_written += len(buffer)
                buffer = []
                last_write = time.time()
            
            # Exit when everything is done
            if (dns_queue.empty() and http_queue.empty() and 
                results_queue.empty() and stats.completed >= stats.total):
                # Final flush
                if buffer:
                    with get_connection(cfg.db_path) as conn:
                        batch_insert_domains(conn, buffer)
                    stats.db_written += len(buffer)
                return
    
    # Progress reporter
    async def reporter():
        nonlocal last_dns_count, last_http_count
        
        while stats.completed < stats.total:
            await asyncio.sleep(2.0)
            
            # Calculate recent rates
            dns_delta = stats.dns_completed - last_dns_count
            http_delta = stats.http_completed - last_http_count
            recent_dns.append(dns_delta / 2.0)
            recent_http.append(http_delta / 2.0)
            last_dns_count = stats.dns_completed
            last_http_count = stats.http_completed
            
            avg_dns = sum(recent_dns) / len(recent_dns) if recent_dns else 0
            avg_http = sum(recent_http) / len(recent_http) if recent_http else 0
            
            pct = stats.completed / stats.total * 100
            print(f"[{stats.completed:,}/{stats.total:,}] {pct:.1f}% | "
                  f"DNS: {avg_dns:.0f}/s ({stats.dns_success}✓ {stats.dns_failed}✗) | "
                  f"HTTP: {avg_http:.0f}/s ({stats.http_success}✓ {stats.http_failed}✗ {stats.http_blocked}🛡) | "
                  f"Q: dns={dns_queue.qsize()} http={http_queue.qsize()} | "
                  f"ETA: {stats.format_eta()}")
    
    # Setup HTTP clients - SHARDED to avoid pool exhaustion
    # Each shard gets its own connection pool
    num_shards = 10
    workers_per_shard = cfg.http_workers // num_shards
    
    limits = httpx.Limits(
        max_keepalive_connections=50,
        max_connections=200,  # 200 per shard = 2000 total
        keepalive_expiry=cfg.keepalive_expiry
    )
    timeout = httpx.Timeout(cfg.http_timeout, connect=1.0)
    
    # Create multiple clients
    clients = []
    for i in range(num_shards):
        client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": cfg.user_agent},
            follow_redirects=True,
            limits=limits,
            http2=False
        )
        clients.append(client)
    
    print(f"Created {num_shards} HTTP client shards ({workers_per_shard} workers each)")
    
    try:
        # Fill DNS queue
        for domain in domains:
            await dns_queue.put(domain)
        
        print(f"Queued {total:,} domains for processing")
        print(f"Starting {cfg.dns_workers} DNS workers + {cfg.http_workers} HTTP workers...")
        
        # Start workers - assign to shards round-robin
        dns_tasks = [asyncio.create_task(dns_worker()) for _ in range(cfg.dns_workers)]
        http_tasks = []
        for i in range(cfg.http_workers):
            shard_idx = i % num_shards
            task = asyncio.create_task(http_worker(clients[shard_idx]))
            http_tasks.append(task)
        
        db_task = asyncio.create_task(db_writer())
        reporter_task = asyncio.create_task(reporter())
        
        # Wait for DNS to complete
        await dns_queue.join()
        
        # Signal DNS workers to stop
        for _ in range(cfg.dns_workers):
            await dns_queue.put(None)
        await asyncio.gather(*dns_tasks)
        
        # Wait for HTTP to complete
        await http_queue.join()
        
        # Signal HTTP workers to stop
        for _ in range(cfg.http_workers):
            await http_queue.put(None)
        await asyncio.gather(*http_tasks)
        
        # Wait for DB writer
        await results_queue.join()
        db_task.cancel()
        reporter_task.cancel()
        
    finally:
        # Close all clients
        for client in clients:
            await client.aclose()
    
    # Final stats
    print(f"\n{'='*70}")
    print(f"PIPELINE COMPLETE")
    print(f"{'='*70}")
    print(f"Total processed:      {stats.completed:,}")
    print(f"DNS success:          {stats.dns_success:,}")
    print(f"DNS failed:           {stats.dns_failed:,}")
    print(f"HTTP success:         {stats.http_success:,}")
    print(f"HTTP failed:          {stats.http_failed:,}")
    print(f"HTTP blocked:         {stats.http_blocked:,}")
    print(f"Time elapsed:         {stats.elapsed:.1f}s ({stats.elapsed/60:.1f}m)")
    print(f"Overall rate:         {stats.overall_rate:.1f}/s")
    print(f"{'='*70}")


def parse_args():
    p = argparse.ArgumentParser(description="Pipeline-based high performance fetcher")
    p.add_argument("--input", "-i", required=True, help="Input CSV file")
    p.add_argument("--db", default="wxawebcat.db", help="Database path")
    p.add_argument("--limit", "-n", type=int, help="Limit domains")
    p.add_argument("--dns-workers", type=int, default=100, help="DNS worker count")
    p.add_argument("--http-workers", type=int, default=500, help="HTTP worker count")
    p.add_argument("--dns-server", default="165.232.131.164", help="DNS server")
    p.add_argument("--timeout", "-t", type=float, default=2.0, help="Timeout in seconds")
    return p.parse_args()


def main():
    args = parse_args()
    print(f"\n🚀 PIPELINE FETCHER")
    print(f"   DNS workers: {args.dns_workers}")
    print(f"   HTTP workers: {args.http_workers}")
    print(f"   Timeout: {args.timeout}s\n")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
