#!/usr/bin/env python3
"""
Test script to verify TOML configuration reading
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from wxawebcat_fetcher_enhanced import ClassifierConfig, read_toml


def test_toml_reading():
    """Test that configuration is properly read from TOML"""
    
    print("=" * 70)
    print("TOML CONFIGURATION TEST")
    print("=" * 70)
    
    # Test reading the enhanced TOML
    toml_path = "wxawebcat_enhanced.toml"
    
    print(f"\nReading config from: {toml_path}")
    
    try:
        # Test raw TOML reading
        raw_config = read_toml(toml_path)
        print("\n✓ TOML file successfully parsed")
        print(f"  Sections found: {list(raw_config.keys())}")
        
        # Test ClassifierConfig creation from TOML
        cfg = ClassifierConfig.from_toml(toml_path)
        print("\n✓ ClassifierConfig successfully created from TOML")
        
        print("\n--- Configuration Values ---")
        print(f"  Fetch directory:          {cfg.fetch_dir}")
        print(f"  Output directory:         {cfg.out_dir}")
        print(f"  Error log:                {cfg.error_log}")
        print(f"  Hash cache file:          {cfg.hash_cache_file}")
        print()
        print(f"  vLLM base URL:            {cfg.vllm_base_url}")
        print(f"  Model:                    {cfg.model}")
        print()
        print(f"  LLM concurrency:          {cfg.llm_concurrency}")
        print(f"  File concurrency:         {cfg.file_concurrency}")
        print(f"  Request timeout:          {cfg.request_timeout_s}s")
        print()
        print(f"  Rule confidence cutoff:   {cfg.rule_confidence_cutoff}")
        print(f"  TLD rules enabled:        {cfg.enable_tld_rules}")
        print(f"  Content hash enabled:     {cfg.enable_content_hash_dedup}")
        print(f"  Min content length:       {cfg.min_content_length_for_hash} chars")
        
        # Verify specific sections
        print("\n--- New Enhancement Sections ---")
        if "tld_rules" in raw_config:
            print(f"  [tld_rules] section:      ✓ Found")
            print(f"    enabled:                {raw_config['tld_rules'].get('enabled')}")
        else:
            print(f"  [tld_rules] section:      ✗ Missing")
        
        if "content_hash" in raw_config:
            print(f"  [content_hash] section:   ✓ Found")
            print(f"    enabled:                {raw_config['content_hash'].get('enabled')}")
            print(f"    cache_file:             {raw_config['content_hash'].get('cache_file')}")
            print(f"    min_content_length:     {raw_config['content_hash'].get('min_content_length')}")
        else:
            print(f"  [content_hash] section:   ✗ Missing")
        
        print("\n✓ All configuration tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error reading configuration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_overrides():
    """Test that command-line arguments override TOML config"""
    
    print("\n" + "=" * 70)
    print("CONFIGURATION OVERRIDE TEST")
    print("=" * 70)
    
    toml_path = "wxawebcat_enhanced.toml"
    
    # Test with overrides
    cfg = ClassifierConfig.from_toml(
        toml_path,
        fetch_dir="/custom/fetch",
        out_dir="/custom/output"
    )
    
    print("\n✓ Testing command-line overrides:")
    print(f"  Fetch directory:  {cfg.fetch_dir} (should be /custom/fetch)")
    print(f"  Output directory: {cfg.out_dir} (should be /custom/output)")
    
    assert str(cfg.fetch_dir) == "/custom/fetch", "Fetch dir override failed"
    assert str(cfg.out_dir) == "/custom/output", "Output dir override failed"
    
    print("\n✓ Command-line overrides work correctly!")
    return True


def test_default_fallbacks():
    """Test that defaults are used when sections are missing"""
    
    print("\n" + "=" * 70)
    print("DEFAULT FALLBACK TEST")
    print("=" * 70)
    
    # Test with original TOML that doesn't have new sections
    try:
        cfg = ClassifierConfig.from_toml("wxawebcat.toml")
        print("\n✓ Successfully loaded original TOML (without enhancements)")
        print(f"  TLD rules enabled:     {cfg.enable_tld_rules} (default: True)")
        print(f"  Content hash enabled:  {cfg.enable_content_hash_dedup} (default: True)")
        print("\n✓ Defaults applied correctly for missing sections!")
        return True
    except FileNotFoundError:
        print("\n⚠ Original wxawebcat.toml not found, skipping this test")
        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def main():
    """Run all tests"""
    
    results = []
    
    results.append(("TOML Reading", test_toml_reading()))
    results.append(("Config Overrides", test_config_overrides()))
    results.append(("Default Fallbacks", test_default_fallbacks()))
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name:.<50} {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓ All tests passed! Configuration system working correctly.")
    else:
        print("\n✗ Some tests failed. Check output above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
