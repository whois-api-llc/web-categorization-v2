#!/bin/bash
# Verify EXTREME config has correct settings

echo "=== Verifying wxawebcat_extreme.toml ==="
echo ""

if [ ! -f wxawebcat_extreme.toml ]; then
    echo "❌ ERROR: wxawebcat_extreme.toml not found!"
    exit 1
fi

echo "Checking settings:"
echo ""

# Check fetch_concurrency
fc=$(grep "fetch_concurrency" wxawebcat_extreme.toml | grep -v "#" | grep -o "[0-9]*")
echo "fetch_concurrency: $fc (should be 250)"
if [ "$fc" = "250" ]; then
    echo "  ✅ Correct!"
else
    echo "  ❌ WRONG! Should be 250"
fi

# Check dns_concurrency  
dc=$(grep "dns_concurrency" wxawebcat_extreme.toml | grep -v "#" | grep -o "[0-9]*")
echo "dns_concurrency: $dc (should be 100)"
if [ "$dc" = "100" ]; then
    echo "  ✅ Correct!"
else
    echo "  ❌ WRONG! Should be 100"
fi

# Check batch_size
bs=$(grep "batch_size" wxawebcat_extreme.toml | head -1 | grep -o "[0-9]*")
echo "batch_size: $bs (should be 1000)"
if [ "$bs" = "1000" ]; then
    echo "  ✅ Correct!"
else
    echo "  ❌ WRONG! Should be 1000"
fi

# Check delay_ms
dm=$(grep "delay_ms" wxawebcat_extreme.toml | grep -o "[0-9]*")
echo "delay_ms: $dm (should be 1)"
if [ "$dm" = "1" ]; then
    echo "  ✅ Correct!"
else
    echo "  ❌ WRONG! Should be 1"
fi

echo ""
echo "=== Verification Complete ==="
