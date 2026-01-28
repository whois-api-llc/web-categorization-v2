#!/usr/bin/env python3
"""
Demo script to show TLD classification and content hash deduplication improvements
"""

import json
from pathlib import Path

# Import the enhanced functions
import sys
sys.path.insert(0, str(Path(__file__).parent))

from wxawebcat_fetcher_enhanced import (
    classify_by_tld,
    extract_tld,
    TLD_CATEGORY_MAP,
    ContentHashCache,
    build_content_fingerprint,
    rule_preclass,
)


def demo_tld_classification():
    """Demonstrate TLD-based classification"""
    print("=" * 70)
    print("TLD CLASSIFICATION DEMO")
    print("=" * 70)
    
    test_domains = [
        "whitehouse.gov",
        "nasa.gov",
        "mit.edu",
        "stanford.edu",
        "example.xxx",
        "gambling.xxx",
        "bitcoin.crypto",
        "myart.museum",
        "chase.bank",
        "google.com",  # No special TLD rule
        "example.gov.uk",
        "oxford.ac.uk",
    ]
    
    for domain in test_domains:
        tld = extract_tld(domain)
        result = classify_by_tld(domain)
        
        if result:
            category, confidence, reason = result
            print(f"✓ {domain:25} → TLD: {tld:12} → {category:20} ({confidence:.2f}) - {reason}")
        else:
            print(f"  {domain:25} → TLD: {tld if tld else 'N/A':12} → No TLD rule")
    
    print(f"\nTotal TLD rules configured: {len(TLD_CATEGORY_MAP)}")
    print()


def demo_content_hash_deduplication():
    """Demonstrate content hash deduplication"""
    print("=" * 70)
    print("CONTENT HASH DEDUPLICATION DEMO")
    print("=" * 70)
    
    # Create a temporary cache
    cache = ContentHashCache(Path("./test_hash_cache.json"))
    
    # Simulate three parked domains with identical content
    parked_domains = [
        {
            "fqdn": "parked-domain-1.com",
            "http": {
                "title": "This domain is for sale",
                "body_snippet": "Buy this premium domain today. Contact us at Sedo.",
                "meta": {"description": "Domain for sale"}
            }
        },
        {
            "fqdn": "parked-domain-2.net",
            "http": {
                "title": "This domain is for sale",
                "body_snippet": "Buy this premium domain today. Contact us at Sedo.",
                "meta": {"description": "Domain for sale"}
            }
        },
        {
            "fqdn": "unique-business.com",
            "http": {
                "title": "Acme Corp - Leading Provider of Widget Solutions",
                "body_snippet": "Welcome to Acme Corp. We provide innovative widget solutions for businesses worldwide.",
                "meta": {"description": "Premium widget manufacturer"}
            }
        },
    ]
    
    print("Processing domains...\n")
    
    for doc in parked_domains:
        fqdn = doc["fqdn"]
        content_fp = build_content_fingerprint(doc)
        
        if not content_fp:
            print(f"{fqdn}: No content fingerprint (content too short)")
            continue
        
        content_hash = cache.compute_hash(content_fp)
        cached = cache.get(content_hash)
        
        if cached:
            print(f"🔄 CACHE HIT: {fqdn}")
            print(f"   Similar to: {cached['example_fqdn']}")
            print(f"   Category: {cached['category']} (confidence: {cached['confidence']})")
            print(f"   Hash: {content_hash[:16]}...")
        else:
            print(f"🆕 CACHE MISS: {fqdn}")
            print(f"   Would call LLM for classification")
            print(f"   Hash: {content_hash[:16]}...")
            
            # Simulate storing the result
            cache.put(content_hash, {
                "category": "Parked",
                "confidence": 0.95,
                "example_fqdn": fqdn,
                "cached_at": "2025-01-27T12:00:00Z"
            })
        print()
    
    # Show cache stats
    stats = cache.stats()
    print("Cache Statistics:")
    print(f"  Cache size: {stats['cache_size']}")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Hit rate: {stats['hit_rate']:.1%}")
    
    if stats['misses'] > 0:
        savings_pct = (stats['hits'] / (stats['hits'] + stats['misses'])) * 100
        print(f"  LLM calls saved: {stats['hits']} ({savings_pct:.1f}%)")
    print()


def demo_combined_rules():
    """Demonstrate how TLD and other rules work together"""
    print("=" * 70)
    print("COMBINED RULE ENGINE DEMO")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "Government site (TLD rule)",
            "doc": {
                "fqdn": "cdc.gov",
                "dns": {"rcode": "NOERROR", "a": ["1.2.3.4"]},
                "http": {"status": 200, "title": "CDC - Disease Control"}
            }
        },
        {
            "name": "Parked domain (content rule)",
            "doc": {
                "fqdn": "random-domain.com",
                "dns": {"rcode": "NOERROR", "a": ["5.6.7.8"]},
                "http": {
                    "status": 200,
                    "title": "Domain for Sale - BUY THIS DOMAIN",
                    "body_snippet": "This premium domain is available at Sedo"
                }
            }
        },
        {
            "name": "DNS failure (DNS rule)",
            "doc": {
                "fqdn": "nonexistent.com",
                "dns": {"rcode": "NXDOMAIN"},
                "http": {}
            }
        },
        {
            "name": "Educational institution (TLD rule)",
            "doc": {
                "fqdn": "harvard.edu",
                "dns": {"rcode": "NOERROR", "a": ["1.2.3.4"]},
                "http": {"status": 200, "title": "Harvard University"}
            }
        },
        {
            "name": "Adult content (TLD rule)",
            "doc": {
                "fqdn": "example.xxx",
                "dns": {"rcode": "NOERROR", "a": ["1.2.3.4"]},
                "http": {"status": 200}
            }
        },
    ]
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print(f"FQDN: {test['doc']['fqdn']}")
        
        result = rule_preclass(test['doc'])
        if result:
            category, confidence, reason = result
            print(f"✓ Classified: {category} (confidence: {confidence:.2f})")
            print(f"  Reason: {reason}")
        else:
            print(f"  No rule match → Would use LLM classification")
    print()


def main():
    """Run all demos"""
    demo_tld_classification()
    demo_content_hash_deduplication()
    demo_combined_rules()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✓ TLD Classification: Instant, high-confidence classification for")
    print("  government, education, adult, and other special-purpose TLDs")
    print()
    print("✓ Content Hash Deduplication: Saves 30%+ LLM calls by detecting")
    print("  duplicate content across different domains (parked domains, etc.)")
    print()
    print("Both features integrate seamlessly with the existing rule engine!")
    print("=" * 70)


if __name__ == "__main__":
    main()
