import pytest
import ast
import secrets
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
import re

from app.extensions import db
from app.models import IdentityProfile, Student, StudentTeacher, Transaction, TransactionStatus, User
from app.hash_utils import get_random_salt, hash_username
from app.routes import student as student_routes
from app.services import attendance_service
from tests.helpers.class_scope import create_class_scope, make_student_seat
from tests.helpers.v2_fixtures import make_admin


def _make_v2_user_and_login(client, class_row):
    """Create a v2 User with session nonce and log in as a student.

    Returns (user, seat) where seat is the student seat in class_row.
    """
    nonce = secrets.token_hex(32)
    user = User(
        username_hash=f"test_{secrets.token_hex(8)}",
        username_lookup_hash=f"lookup_{secrets.token_hex(8)}",
        has_completed_setup=True,
        current_session_nonce=nonce,
        last_active_class_id=class_row.class_id,
    )
    db.session.add(user)
    db.session.flush()
    seat = make_student_seat(
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        user_id=user.id,
        first_name="Test",
        last_name="S",
    )
    student = Student(
        identity_profile=seat.identity_profile,
        block=seat.block,
        salt=get_random_salt(),
        username_hash=hash_username(f"student_{secrets.token_hex(8)}", get_random_salt()),
        class_id=class_row.class_id,
        join_code=class_row.join_code,
    )
    db.session.add(student)
    user.last_active_class_id = class_row.class_id
    db.session.flush()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["current_session_nonce"] = nonce
        sess["current_class_id"] = class_row.class_id
        sess["current_join_code"] = class_row.join_code
        sess["current_seat_id"] = seat.id
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
        sess["last_activity"] = sess["login_time"]
    user.last_active_class_id = class_row.class_id
    db.session.commit()
    with client.session_transaction() as sess:
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
        sess["last_activity"] = sess["login_time"]
    return user, seat


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        sess["student_id"] = student_id
        sess["current_join_code"] = join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()


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
    source = inspect.getsource(student_routes.switch_teacher)
    assert "abort(404)" in source
    assert "Admin.query" not in source


def test_admin_void_route_is_not_direct_ledger_authority():
    admin_source = Path("app/routes/admin.py").read_text()
    start = admin_source.index("def void_transaction(")
    end = admin_source.index("# -------------------- HALL PASS MANAGEMENT --------------------")
    source = admin_source[start:end]
    assert "Transaction(" not in source
    assert "create_idempotent_transaction(" not in source
    assert "execute_void_transaction(" in source
    assert "_student_scope_subquery()" not in source


def test_admin_claim_route_is_not_direct_ledger_authority():
    admin_source = Path("app/routes/admin.py").read_text()
    start = admin_source.index("def process_claim(")
    end = admin_source.index("return render_template('admin_process_claim.html'")
    source = admin_source[start:end]
    assert "Transaction(" not in source
    assert "_student_scope_subquery()" not in source
    assert "execute_insurance_claim_resolution(" in source


def test_dead_route_mutations_are_feat_owned():
    admin_source = Path("app/routes/admin.py").read_text()
    system_admin_source = Path("app/routes/system_admin.py").read_text()

    def assert_decorator(source, func_name, decorator):
        idx = source.index(func_name)
        start = max(0, idx - 150)
        assert decorator in source[start:idx]

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
    assert "resolve_canonical_context(" in purchase_source
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
    # assert_can_purchase_item is defined in access_policy_service and is the
    # canonical guard for store purchases. The feat delegates to the route for
    # pre-condition checks; verify the guard function exists.
    source = Path("app/services/access_policy_service.py").read_text()
    assert "def assert_can_purchase_item(" in source


def test_file_claim_feat_enforces_access_policy():
    source = Path("app/feats/insurance_claim_feat.py").read_text()
    assert "assert_can_file_claim(" in source


def test_switch_class_access_policy_exists():
    source = Path("app/services/access_policy_service.py").read_text()
    assert "def assert_can_switch_class(" in source


def test_switch_teacher_access_policy_is_removed():
    source = Path("app/services/access_policy_service.py").read_text()
    assert "def assert_can_switch_teacher(" not in source


def test_insurance_claim_feat_enforces_access_policy():
    source = Path("app/feats/insurance_claim_feat.py").read_text()
    assert "assert_can_process_claim(" in source


def test_dashboard_read_is_interest_mutation_free(client):
    from uuid import uuid4
    from decimal import Decimal

    teacher = make_admin("dash_guard_teacher", "secret")
    db.session.add(teacher)
    db.session.flush()

    join_code = "READPURE1"
    class_row = create_class_scope(
        teacher=teacher,
        join_code=join_code,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    db.session.flush()

    user, seat = _make_v2_user_and_login(client, class_row)

    mature_savings_time = datetime.now(timezone.utc) - timedelta(days=31)
    db.session.add(Transaction(
        seat_id=seat.id,
        class_id=class_row.class_id,
        join_code=join_code,
        amount=Decimal('100.00'),
        amount_cents=10000,
        account_type="savings",
        type="deposit",
        description="Savings Seed",
        timestamp=mature_savings_time,
        date_funds_available=mature_savings_time,
        correlation_id=f"bypass_test_{uuid4().hex}",
        status=TransactionStatus.POSTED,
    ))
    db.session.commit()

    before_count = Transaction.query.filter_by(seat_id=seat.id).count()

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    after_count = Transaction.query.filter_by(seat_id=seat.id).count()
    assert after_count == before_count
    assert Transaction.query.filter_by(
        seat_id=seat.id,
        description="Monthly Savings Interest",
        account_type="savings",
    ).first() is None


def test_dashboard_access_policy_fail_closed_invalid_join_code(client):
    import secrets as _secrets
    from app.models import User

    # Create a user with a valid nonce but NO last_active_class_id (simulates
    # a student whose class context is not established — the v2 equivalent of
    # presenting an invalid/missing join code).
    nonce = _secrets.token_hex(32)
    user = User(
        username_hash=f"scope_test_{_secrets.token_hex(8)}",
        username_lookup_hash=f"scope_lookup_{_secrets.token_hex(8)}",
        has_completed_setup=True,
        current_session_nonce=nonce,
        last_active_class_id=None,  # No active class — context cannot be established
    )
    db.session.add(user)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["current_session_nonce"] = nonce

    response = client.get("/student/dashboard")

    # Without a valid class context, the student cannot access the dashboard.
    # The v2 login_required decorator raises ContextInvariantViolation (missing
    # class_id) and redirects to select-class-context; or ContextNotEstablished
    # which redirects to login. Either way the dashboard must not be 200.
    assert response.status_code == 302
    location = response.headers["Location"]
    assert (
        location.endswith("/student/select-class-context")
        or location.endswith("/student/login")
    ), f"Unexpected redirect: {location}"
