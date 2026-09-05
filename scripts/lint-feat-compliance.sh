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
# `app/services/ledger_service.py` was decomposed into per-concern services; the
# four listed below are its write paths (the read/query/verification services do
# not mutate). Named individually rather than by glob because this list is a
# deliberate zero-tolerance roster, not a directory scan — a new ledger service
# should have to be added here on purpose.
TIER1_FILES=(
    "app/services/ledger_command_service.py"
    "app/services/ledger_correction_service.py"
    "app/services/ledger_posting_service.py"
    "app/services/ledger_settlement_service.py"
    "app/services/ledger_transfer_service.py"
    "app/payroll.py"
    "app/utils/banking.py"
    "app/routes/recovery.py"
)

echo "🔍 Checking for FEAT Constitutional violations..."

# Identify commits whose enclosing function has no canonical FEAT context.
VIOLATIONS=$(python3 - <<'PY'
import ast
from pathlib import Path

class CommitVisitor(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.function_depth = 0
        self.lines = []
    def visit_FunctionDef(self, node):
        self._visit_function(node)
    def visit_AsyncFunctionDef(self, node):
        self._visit_function(node)
    def _visit_function(self, node):
        has_feat = any(
            isinstance(dec, ast.Call)
            and getattr(dec.func, 'id', None) == 'requires_feat_context'
            for dec in node.decorator_list
        )
        if not has_feat:
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                for call in ast.walk(sub):
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                            and call.func.attr == 'commit'
                            and isinstance(call.func.value, ast.Attribute)
                            and call.func.value.attr == 'session'):
                        self.lines.append(f'{self.path}:{call.lineno}:        db.session.commit()')
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)

for path in Path('app').rglob('*.py'):
    if str(path).startswith('app/feats/'):
        continue
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:
        continue
    visitor = CommitVisitor(path)
    visitor.visit(tree)
    for line in visitor.lines:
        print(line)
PY
)
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

    # FEAT COVERAGE CHECK: Tier 1 files must have at least one canonical FEAT boundary
    for file in "${TIER1_FILES[@]}"; do
        if ! grep -q "@requires_feat_context" "$file"; then
            echo "🚨 COVERAGE MISSING: $file has zero canonical FEAT coverage."
            TIER1_VIOLATIONS=$((TIER1_VIOLATIONS + 1))
        fi
    done

    if [ "$TIER1_VIOLATIONS" -gt 0 ]; then
        echo "❌ Wave 1 blocked: Critical files contain direct commits or lack FEAT coverage."
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
