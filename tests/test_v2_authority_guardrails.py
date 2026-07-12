import pytest
import ast
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
import re

from app.extensions import db
from app.models import IdentityProfile, User, UserRole, Transaction, Seat
from app.routes import student as student_routes
from app.services import attendance_service
from tests.helpers.class_scope import create_class_scope
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.canonical_session import set_canonical_context


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        seat = Seat.query.filter_by(user_id=student_id).order_by(Seat.id.asc()).first()
        if seat:
            set_canonical_context(
                sess,
                user_id=student_id,
                class_id=seat.class_id,
                seat_id=seat.id,
                role="student",
            )


def test_student_dashboard_does_not_trigger_hidden_mutation_calls():
    source = inspect.getsource(student_routes.dashboard)
    assert "apply_savings_interest(" not in source
    assert "_ensure_rent_hall_pass_top_off(" not in source
    assert "resolve_scope(" in source
    assert "assert_can_view_dashboard(" in source
    assert "get_current_class_context()" not in source


def test_student_shop_does_not_trigger_collective_goal_reconciliation():
    source = inspect.getsource(student_routes.shop)
    assert "process_expired_collective_goals(" not in source


def test_route_modules_do_not_use_legacy_balance_properties():
    route_sources = {
        path.name: path.read_text()
        for path in [
            Path("app/routes/student.py"),
            Path("app/routes/api.py"),
            Path("app/routes/admin.py"),
        ]
    }
    for name, source in route_sources.items():
        assert ".checking_balance" not in source, f"{name} still uses model-level checking balance authority"
        assert ".savings_balance" not in source, f"{name} still uses model-level savings balance authority"


def test_attendance_service_does_not_compute_pay_or_pull_internal_payroll_anchors():
    source = inspect.getsource(attendance_service)
    assert "get_pay_rate_for_block" not in source
    assert "get_last_payroll_time(" not in source


def test_rent_pay_route_is_not_direct_ledger_or_obligations_authority():
    source = inspect.getsource(student_routes.rent_pay)
    assert "Transaction(" not in source
    assert "RentPayment(" not in source
    assert "resolve_canonical_context(" in source
    assert "execute_rent_payment(" in source


def test_transfer_route_is_not_direct_ledger_authority():
    source = inspect.getsource(student_routes.transfer)
    assert "Transaction(" not in source
    assert "execute_account_transfer(" in source


def test_purchase_insurance_route_is_not_direct_ledger_or_obligations_authority():
    source = inspect.getsource(student_routes.purchase_insurance)
    assert "Transaction(" not in source
    assert "StudentInsurance(" not in source
    assert "execute_insurance_purchase(" in source


def test_file_claim_route_is_not_direct_obligations_authority():
    source = inspect.getsource(student_routes.file_claim)
    assert "InsuranceClaim(" not in source
    assert "db.session.add(claim)" not in source
    assert "resolve_scope(" in source
    assert "execute_file_claim(" in source


def test_switch_class_route_uses_access_scope_boundary():
    source = inspect.getsource(student_routes.switch_class)
    assert "resolve_student_class_switch_scope(" in source
    assert "assert_can_switch_class(" in source
    assert "TeacherBlock.query.filter_by(" not in source


def test_switch_teacher_role_specific_public_id_route_is_disabled():
    # Route was removed in v2; verify it is no longer registered.
    assert not hasattr(student_routes, "switch_teacher"), (
        "switch_teacher route must remain removed; it exposed a role-specific identity endpoint."
    )


def test_admin_void_route_is_not_direct_ledger_authority():
    admin_source = Path("app/routes/admin.py").read_text()
    start = admin_source.index("def void_transaction(")
    end = admin_source.index("# -------------------- HALL PASS MANAGEMENT --------------------")
    source = admin_source[start:end]
    assert "Transaction(" not in source
    assert "create_idempotent_transaction(" not in source
    assert "execute_void_transaction(" in source
    # v2: class-scoping via canonical context, not legacy resolve_scope
    assert "canonical_context" in source or "resolve_canonical_context(" in source
    assert "_student_scope_subquery()" not in source


def test_admin_claim_route_is_not_direct_ledger_authority():
    admin_source = Path("app/routes/admin.py").read_text()
    start = admin_source.index("def process_claim(")
    end = admin_source.index("return render_template('admin_process_claim.html'")
    source = admin_source[start:end]
    assert "Transaction(" not in source
    # v2: class-scoping via canonical context, not legacy resolve_scope
    assert "canonical_context" in source or "resolve_canonical_context(" in source
    assert "_student_scope_subquery()" not in source
    assert "execute_insurance_claim_resolution(" in source


def test_dead_route_mutations_are_feat_owned():
    admin_source = Path("app/routes/admin.py").read_text()
    system_admin_source = Path("app/routes/system_admin.py").read_text()

    def assert_decorator(source, func_name, decorator):
        idx = source.index(func_name)
        start = max(0, idx - 150)
        assert decorator in source[start:idx]

    def assert_feat_context_in_func(source, func_name, feat_id):
        """Assert that the function body contains FEATContext or feat_shell with the given feat_id."""
        start = source.index(func_name)
        # Use next route decorator as boundary to avoid stopping at inline decorators
        end = source.find("\n@admin_bp.route(", start + 1)
        if end == -1:
            end = source.find("\n@system_admin_bp.route(", start + 1)
        func_body = source[start:end] if end != -1 else source[start:]
        has_feat_shell = f'@feat_shell("{feat_id}")' in source[max(0, start-150):start]
        has_feat_context = "FEATContext(" in func_body and f'"{feat_id}"' in func_body
        assert has_feat_shell or has_feat_context, (
            f"{func_name} must be guarded by @feat_shell or FEATContext with {feat_id}"
        )

    assert_feat_context_in_func(admin_source, "def process_claim(", "FEAT-ADMN-001")
    assert_decorator(admin_source, "def resolve_issue(", "@feat_shell(\"FEAT-ADMN-001\")")
    assert_decorator(admin_source, "def passkey_auth_finish(", "@feat_shell(\"FEAT-ADMN-001\")")
    assert_decorator(system_admin_source, "def resolve_escalated_issue(", "@feat_shell(\"FEAT-OPS-001\")")
    assert_decorator(system_admin_source, "def passkey_auth_finish(", "@feat_shell(\"FEAT-OPS-001\")")


def test_admin_get_routes_remain_read_only():
    admin_source = Path("app/routes/admin.py").read_text()
    def get_func_source(source, func_name):
        start = source.index(func_name)
        end = source.find("@admin_bp.route(", start + 1)
        return source[start:end] if end != -1 else source[start:]

    banking_source = get_func_source(admin_source, "def banking():")
    assert "BankingSettings(" not in banking_source
    assert "db.session.commit()" not in banking_source
    assert "db.session.flush()" not in banking_source

    recovery_source = get_func_source(admin_source, "def recovery_status():")
    assert "db.session.commit()" not in recovery_source
    assert "db.session.flush()" not in recovery_source
    assert "recovery_request.status = 'expired'" not in recovery_source

def test_admin_adjustment_routes_use_adjustment_feat():
    admin_source = Path("app/routes/admin.py").read_text()
    for fn_name in [
        "def give_bonus_all(",
        "def payroll_apply_reward(",
        "def payroll_apply_fine(",
        "def payroll_manual_payment(",
        "def run_payroll(",
    ]:
        if fn_name not in admin_source:
            continue
        start = admin_source.index(fn_name)
        next_route = admin_source.find("@admin_bp.route(", start + 1)
        source = admin_source[start: next_route if next_route != -1 else None]
        assert "execute_admin_adjustments(" in source, f"{fn_name} does not delegate to admin adjustment feat"


def test_transaction_constructor_is_only_used_in_ledger_service():
    allowed = {
        Path("app/services/ledger_service.py"),
        Path("app/utils/transaction_idempotency.py"),
    }
    hits = []
    for path in Path("app").rglob("*.py"):
        source = path.read_text()
        if path in allowed:
            continue
        tree = ast.parse(source, filename=str(path))
        has_constructor_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Transaction"
            for node in ast.walk(tree)
        )
        if has_constructor_call:
            hits.append(str(path))
    assert hits == [], f"Transaction constructor leaked outside ledger_service: {hits}"


def test_store_purchase_route_is_not_direct_ledger_or_store_authority():
    purchase_source = inspect.getsource(__import__("app.routes.api", fromlist=["purchase_item"]).purchase_item)
    assert "Transaction(" not in purchase_source
    assert "StudentItem(correlation_id='corr_test', " not in purchase_source
    # v2: route uses canonical context, not legacy resolve_scope
    assert "canonical_context" in purchase_source or "resolve_canonical_context(" in purchase_source
    assert "execute_store_purchase(" in purchase_source
    assert "execute_rent_perk_purchase(" in purchase_source
    assert "db.session.commit()" not in purchase_source


def test_feat_modules_do_not_construct_transactions_or_write_rows_directly():
    for path in [
        Path("app/feats/rent_payment_feat.py"),
        Path("app/feats/store_purchase_feat.py"),
        Path("app/feats/transfer_feat.py"),
        Path("app/feats/insurance_purchase_feat.py"),
        Path("app/feats/insurance_claim_feat.py"),
        Path("app/feats/transaction_void_feat.py"),
        Path("app/feats/admin_adjustment_feat.py"),
    ]:
        source = path.read_text()
        assert "Transaction(" not in source
        assert "db.session.add(" not in source
        assert "StudentItem(correlation_id='corr_test', " not in source
        assert "RentPayment(" not in source
        assert "db.session.rollback(" not in source


def test_rent_payment_feat_enforces_access_policy():
    source = Path("app/feats/rent_payment_feat.py").read_text()
    assert "assert_can_pay_rent(" in source


def test_store_purchase_feat_enforces_access_policy():
    source = Path("app/feats/store_purchase_feat.py").read_text()
    # v2: feat is guarded by requires_feat_context; item visibility is enforced by store_service
    assert "requires_feat_context(" in source


def test_file_claim_feat_enforces_access_policy():
    source = Path("app/feats/insurance_claim_feat.py").read_text()
    assert "assert_can_file_claim(" in source


def test_switch_class_access_policy_exists():
    source = Path("app/services/access_policy_service.py").read_text()
    assert "def assert_can_switch_class(" in source


def test_insurance_claim_feat_enforces_access_policy():
    source = Path("app/feats/insurance_claim_feat.py").read_text()
    assert "assert_can_process_claim(" in source


def test_dashboard_read_is_interest_mutation_free(client):
    from app.feats.base import FEATContext
    from app.services import ledger_service
    from tests.helpers.class_scope import make_student_identity

    teacher = make_admin("dash_guard_teacher")
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="READPURE1", display_name="A", section="A")
    seat = make_student_identity(class_id=class_row.class_id, first_name="Read", last_name="P", claimed=True)

    mature_savings_time = datetime.now(timezone.utc) - timedelta(days=31)
    with FEATContext("FEAT-IDEN-001", idempotency_key="test_dashboard_read_seed_tx"):
        ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            amount=100.0,
            account_type="savings",
            type="credit",
            description="Savings Seed",
        )

    user_id = seat.user_id
    db.session.commit()
    db.session.remove()

    before_count = Transaction.query.filter_by(user_id=user_id).count()
    _login_student(client, user_id, "READPURE1")

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    after_count = Transaction.query.filter_by(user_id=user_id).count()
    assert after_count == before_count
    assert Transaction.query.filter_by(
        user_id=user_id,
        description="Monthly Savings Interest",
        account_type="savings",
    ).first() is None


def test_dashboard_access_policy_fail_closed_no_canonical_context(client):
    """Dashboard must redirect to select-class-context when the user has no canonical class context.

    v2 semantics: class authority lives in user.last_active_class_id (DB), not in
    session["current_join_code"]. When last_active_class_id is absent/cleared the
    dashboard cannot establish a CanonicalContext and must redirect rather than serve.
    """
    from tests.helpers.class_scope import make_student_identity

    teacher = make_admin("dash_scope_teacher")
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code="DASHACLSS", display_name="A", section="A")
    seat = make_student_identity(class_id=class_a.class_id, first_name="Scope", last_name="Q", claimed=True)
    user_id = seat.user_id
    db.session.commit()
    db.session.remove()

    # Log in with user_id + valid nonce but WITHOUT writing last_active_class_id/seat_id,
    # so resolve_canonical_context() cannot establish class context.
    import secrets
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    from app.feats.base import FEATContext
    from app.models import User
    from app.extensions import db as _db
    nonce = secrets.token_urlsafe(32)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"test_no_ctx_nonce:{user_id}"):
        user = _db.session.get(User, user_id)
        user.current_session_nonce = nonce
        user.last_active_class_id = None
        user.last_active_seat_id = None
        _db.session.flush()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["current_session_nonce"] = nonce
        sess["login_time"] = now_iso
        sess["last_activity"] = now_iso

    response = client.get("/student/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student/select-class-context")
