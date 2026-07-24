#!/bin/bash
# scripts/lint-feat-compliance.sh
# 
# FEAT CONSTITUTIONAL ENFORCEMENT
# This script identifies illegal database commits outside of the FEAT orchestration layer.

set -e

# Configuration
FEAT_DIR="app/feats"
EXCLUDE_DIR="app/feats"
EXPECTED_VIOLATIONS=150  # Hardcoded baseline for Wave 1 containment

# Tier 1 Critical Files (Zero Tolerance once wrapped)
TIER1_FILES=(
    "app/services/ledger_service.py"
    "app/payroll.py"
    "app/utils/banking.py"
    "app/routes/recovery.py"
)

echo "🔍 Checking for FEAT Constitutional violations..."

# Grep for illegal commits, ignoring authorized legacy wraps and shell-authorized commits
VIOLATIONS=$(grep -r "db.session.commit()" app --exclude-dir=$EXCLUDE_DIR -n | grep -v "# FEAT-LEGACY-WRAP" | grep -v "# FEAT-AUTHORIZED-SHELL" || true)
COUNT=$(echo "$VIOLATIONS" | grep -v "^$" | wc -l | xargs)

# Grep for direct Transaction instantiation (must use create_idempotent_transaction)
DIRECT_TX=$(grep -rE "\\bTransaction\\(" app --exclude-dir="$EXCLUDE_DIR" --exclude="models.py" -n | grep -v "app/utils/transaction_idempotency.py" | grep -v "# FEAT-AUTHORIZED-DIRECT-TX" || true)
TX_COUNT=$(echo "$DIRECT_TX" | grep -v "^$" | wc -l | xargs)

COUNT=$((COUNT + TX_COUNT))
VIOLATIONS=$(echo -e "$VIOLATIONS\n$DIRECT_TX")

if [ "$COUNT" -gt 0 ]; then
    echo "❌ ERROR: Illegal database commits detected outside of FEAT layer!"
    echo "All state mutations MUST be orchestrated by a compliant FEAT unit in $FEAT_DIR."
    echo ""
    echo "Violations found (first 20):"
    echo "$VIOLATIONS" | head -n 20
    if [ "$COUNT" -gt 20 ]; then
        echo "... and $((COUNT - 20)) more."
    fi
    echo ""
    echo "Total violations:      $COUNT"
    echo "Expected (Baseline):   $EXPECTED_VIOLATIONS"

    # REGRESSION BLOCKER: Fail if violations INCREASE
    if [ "$COUNT" -gt "$EXPECTED_VIOLATIONS" ]; then
        echo "🚨 REGRESSION DETECTED: New violations added ($COUNT > $EXPECTED_VIOLATIONS). Blocking build."
        exit 1
    fi

    # TIER 1 BLOCKER: Fail if any Tier 1 violations are detected (excluding wrapped ones)
    TIER1_VIOLATIONS=0
    for file in "${TIER1_FILES[@]}"; do
        if echo "$VIOLATIONS" | grep -q "$file"; then
            echo "🚨 TIER 1 VIOLATION: $file must be wrapped in a FEAT shell immediately."
            TIER1_VIOLATIONS=$((TIER1_VIOLATIONS + 1))
        fi
    done

    # SHELL COVERAGE CHECK: Tier 1 files must have at least one @feat_shell
    for file in "${TIER1_FILES[@]}"; do
        if ! grep -q "@feat_shell" "$file" && ! grep -q "@requires_feat_context" "$file"; then
            echo "🚨 COVERAGE MISSING: $file has zero FEAT shell coverage."
            TIER1_VIOLATIONS=$((TIER1_VIOLATIONS + 1))
        fi
    done

    if [ "$TIER1_VIOLATIONS" -gt 0 ]; then
        echo "❌ Wave 1 blocked: Critical files contain direct commits or lack shell coverage."
        if [ "$FEAT_STRICT_LINT" = "true" ]; then
            exit 1
        fi
    fi

    # Phase 3 warning
    if [ "$FEAT_STRICT_LINT" = "true" ]; then
        echo "🚨 STRICT MODE ENABLED: Failing build due to architectural non-compliance."
        exit 1
    fi
    
    echo "⚠️  WARNING: System is in transition. Please migrate these to FEAT units."
else
    echo "✅ SUCCESS: No FEAT Constitutional violations detected."
fi
