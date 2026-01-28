#!/usr/bin/env python3
"""
wxawebcat_db.py - Database utilities for wxawebcat

Provides database initialization, connection management, and common queries.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from contextlib import contextmanager


DEFAULT_DB_PATH = "wxawebcat.db"


def init_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize database with schema"""
    print(f"Initializing database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Read schema
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        # Embedded schema if file not found
        schema = """
        -- Minimal embedded schema
        CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fqdn TEXT NOT NULL UNIQUE,
            dns_data TEXT,
            http_data TEXT,
            fetched_at TEXT NOT NULL,
            fetch_status TEXT NOT NULL DEFAULT 'success',
            fetch_error TEXT,
            classified INTEGER NOT NULL DEFAULT 0,
            classified_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_id INTEGER NOT NULL,
            fqdn TEXT NOT NULL,
            method TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence REAL NOT NULL,
            reason TEXT,
            iab_tier1_id TEXT,
            iab_tier1_name TEXT,
            iab_tier2_id TEXT,
            iab_tier2_name TEXT,
            is_sensitive INTEGER DEFAULT 0,
            sensitive_categories TEXT,
            signals TEXT,
            llm_raw TEXT,
            content_hash TEXT,
            classified_at TEXT NOT NULL DEFAULT (datetime('now')),
            iab_enriched INTEGER DEFAULT 0,
            iab_enriched_at TEXT,
            FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS content_hash_cache (
            content_hash TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            confidence REAL NOT NULL,
            example_fqdn TEXT NOT NULL,
            cached_at TEXT NOT NULL DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 1
        );
        
        CREATE INDEX IF NOT EXISTS idx_domains_fqdn ON domains(fqdn);
        CREATE INDEX IF NOT EXISTS idx_domains_classified ON domains(classified);
        CREATE INDEX IF NOT EXISTS idx_classifications_domain_id ON classifications(domain_id);
        CREATE INDEX IF NOT EXISTS idx_classifications_fqdn ON classifications(fqdn);
        CREATE INDEX IF NOT EXISTS idx_classifications_content_hash ON classifications(content_hash);
        """
    else:
        schema = schema_path.read_text()
    
    conn.executescript(schema)
    conn.commit()
    conn.close()
    
    print(f"✓ Database initialized: {db_path}")


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH):
    """Context manager for database connections"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_domain(conn: sqlite3.Connection, fqdn: str, dns_data: Dict, http_data: Dict, 
                  fetch_status: str = 'success', fetch_error: Optional[str] = None) -> int:
    """Insert or update a domain fetch result"""
    
    now = datetime.now(timezone.utc).isoformat()
    
    cursor = conn.execute("""
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
        fqdn,
        json.dumps(dns_data),
        json.dumps(http_data),
        now,
        fetch_status,
        fetch_error
    ))
    
    # Get the domain_id
    cursor = conn.execute("SELECT id FROM domains WHERE fqdn = ?", (fqdn,))
    domain_id = cursor.fetchone()[0]
    
    return domain_id


def get_domains_to_classify(conn: sqlite3.Connection, limit: Optional[int] = None) -> List[Dict]:
    """Get domains that need classification"""
    
    query = """
        SELECT id as domain_id, fqdn, dns_data, http_data, fetched_at
        FROM domains
        WHERE classified = 0 AND fetch_status = 'success'
        ORDER BY id
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor = conn.execute(query)
    
    domains = []
    for row in cursor:
        domains.append({
            'domain_id': row['domain_id'],
            'fqdn': row['fqdn'],
            'dns': json.loads(row['dns_data']) if row['dns_data'] else {},
            'http': json.loads(row['http_data']) if row['http_data'] else {},
            'fetched_at': row['fetched_at']
        })
    
    return domains


def insert_classification(conn: sqlite3.Connection, domain_id: int, fqdn: str,
                         method: str, category: str, confidence: float, reason: str,
                         signals: Dict, llm_raw: Optional[Dict] = None,
                         content_hash: Optional[str] = None) -> int:
    """Insert a classification result"""
    
    now = datetime.now(timezone.utc).isoformat()
    
    cursor = conn.execute("""
        INSERT INTO classifications 
        (domain_id, fqdn, method, category, confidence, reason, signals, llm_raw, content_hash, classified_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        domain_id,
        fqdn,
        method,
        category,
        confidence,
        reason,
        json.dumps(signals),
        json.dumps(llm_raw) if llm_raw else None,
        content_hash,
        now
    ))
    
    return cursor.lastrowid


def get_content_hash_cache(conn: sqlite3.Connection, content_hash: str) -> Optional[Dict]:
    """Get cached classification by content hash"""
    
    cursor = conn.execute("""
        SELECT category, confidence, example_fqdn, hit_count
        FROM content_hash_cache
        WHERE content_hash = ?
    """, (content_hash,))
    
    row = cursor.fetchone()
    if row:
        # Update hit count
        conn.execute("""
            UPDATE content_hash_cache 
            SET hit_count = hit_count + 1
            WHERE content_hash = ?
        """, (content_hash,))
        
        return {
            'category': row['category'],
            'confidence': row['confidence'],
            'example_fqdn': row['example_fqdn'],
            'hit_count': row['hit_count']
        }
    
    return None


def insert_content_hash_cache(conn: sqlite3.Connection, content_hash: str,
                              category: str, confidence: float, fqdn: str) -> None:
    """Insert into content hash cache"""
    
    now = datetime.now(timezone.utc).isoformat()
    
    conn.execute("""
        INSERT OR REPLACE INTO content_hash_cache 
        (content_hash, category, confidence, example_fqdn, cached_at)
        VALUES (?, ?, ?, ?, ?)
    """, (content_hash, category, confidence, fqdn, now))


def update_iab_taxonomy(conn: sqlite3.Connection, classification_id: int,
                       iab_tier1_id: str, iab_tier1_name: str,
                       iab_tier2_id: str, iab_tier2_name: str,
                       is_sensitive: bool, sensitive_categories: List[str]) -> None:
    """Update classification with IAB taxonomy"""
    
    now = datetime.now(timezone.utc).isoformat()
    
    conn.execute("""
        UPDATE classifications
        SET iab_tier1_id = ?,
            iab_tier1_name = ?,
            iab_tier2_id = ?,
            iab_tier2_name = ?,
            is_sensitive = ?,
            sensitive_categories = ?,
            iab_enriched = 1,
            iab_enriched_at = ?
        WHERE id = ?
    """, (
        iab_tier1_id,
        iab_tier1_name,
        iab_tier2_id,
        iab_tier2_name,
        1 if is_sensitive else 0,
        json.dumps(sensitive_categories),
        now,
        classification_id
    ))


def get_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Get database statistics"""
    
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total_domains,
            SUM(CASE WHEN classified = 1 THEN 1 ELSE 0 END) as classified,
            SUM(CASE WHEN classified = 0 THEN 1 ELSE 0 END) as unclassified,
            SUM(CASE WHEN fetch_status != 'success' THEN 1 ELSE 0 END) as failed_fetches
        FROM domains
    """)
    
    stats = dict(cursor.fetchone())
    
    # Classification breakdown
    cursor = conn.execute("""
        SELECT method, COUNT(*) as count
        FROM classifications
        GROUP BY method
    """)
    
    stats['by_method'] = {row['method']: row['count'] for row in cursor}
    
    # IAB enrichment status
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total_classifications,
            SUM(CASE WHEN iab_enriched = 1 THEN 1 ELSE 0 END) as iab_enriched
        FROM classifications
    """)
    
    iab_stats = dict(cursor.fetchone())
    stats.update(iab_stats)
    
    return stats


def export_to_csv(conn: sqlite3.Connection, output_path: str) -> None:
    """Export classifications to CSV"""
    
    import csv
    
    cursor = conn.execute("""
        SELECT 
            d.fqdn,
            c.category,
            c.confidence,
            c.method,
            c.iab_tier1_name,
            c.iab_tier2_name,
            c.is_sensitive,
            c.classified_at
        FROM domains d
        JOIN classifications c ON d.id = c.domain_id
        ORDER BY d.fqdn
    """)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['fqdn', 'category', 'confidence', 'method', 
                        'iab_tier1', 'iab_tier2', 'sensitive', 'classified_at'])
        
        for row in cursor:
            writer.writerow(row)
    
    print(f"✓ Exported to {output_path}")


def main():
    """CLI utility for database management"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="wxawebcat database utilities")
    parser.add_argument('--init', action='store_true', help='Initialize database')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--export', help='Export to CSV')
    parser.add_argument('--db', default=DEFAULT_DB_PATH, help='Database path')
    
    args = parser.parse_args()
    
    if args.init:
        init_database(args.db)
    
    if args.stats:
        with get_connection(args.db) as conn:
            stats = get_statistics(conn)
            print("\n=== DATABASE STATISTICS ===")
            print(f"Total domains:        {stats['total_domains']}")
            print(f"Classified:           {stats['classified']}")
            print(f"Unclassified:         {stats['unclassified']}")
            print(f"Failed fetches:       {stats['failed_fetches']}")
            print(f"\nTotal classifications: {stats['total_classifications']}")
            print(f"IAB enriched:         {stats['iab_enriched']}")
            print(f"\nBy method:")
            for method, count in stats['by_method'].items():
                print(f"  {method:15} {count}")
    
    if args.export:
        with get_connection(args.db) as conn:
            export_to_csv(conn, args.export)


if __name__ == "__main__":
    main()
