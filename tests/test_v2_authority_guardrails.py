import pytest
import ast
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
import re

from app.extensions import db
from app.models import IdentityProfile, Student, StudentTeacher, Transaction
from app.routes import student as student_routes
from app.services import attendance_service
from tests.helpers.class_scope import create_class_scope
from tests.helpers.v2_fixtures import make_admin


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
    assert "resolve_scope(" in source
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
    assert "resolve_scope(" in source
    assert "assert_can_void_transaction(" in source
    assert "_student_scope_subquery()" not in source


def test_admin_claim_route_is_not_direct_ledger_authority():
    admin_source = Path("app/routes/admin.py").read_text()
    start = admin_source.index("def process_claim(")
    end = admin_source.index("return render_template('admin_process_claim.html'")
    source = admin_source[start:end]
    assert "Transaction(" not in source
    assert "resolve_scope(" in source
    assert "assert_can_process_claim(" in source
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
    assert "resolve_scope(" in purchase_source
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
    assert "assert_can_purchase_item(" in source


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
    teacher = make_admin("dash_guard_teacher", "secret")
    db.session.add(teacher)
    db.session.flush()

    profile_read = IdentityProfile(profile_type='student', first_name='Read', last_name='P')
    db.session.add(profile_read)
    db.session.flush()
    student = Student(identity_profile=profile_read, block="A", salt=b"salt", has_completed_setup=True)
    db.session.add(student)
    db.session.flush()

    join_code = "READPURE1"
    create_class_scope(
        teacher=teacher,
        join_code=join_code,
        student=student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    mature_savings_time = datetime.now(timezone.utc) - timedelta(days=31)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=100.0,
        account_type="savings",
        description="Savings Seed",
        timestamp=mature_savings_time,
        date_funds_available=mature_savings_time,
    ))
    db.session.commit()

    before_count = Transaction.query.filter_by(student_id=student.id).count()
    _login_student(client, student.id, join_code)

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    after_count = Transaction.query.filter_by(student_id=student.id).count()
    assert after_count == before_count
    assert Transaction.query.filter_by(
        student_id=student.id,
        description="Monthly Savings Interest",
        account_type="savings",
    ).first() is None


def test_dashboard_access_policy_fail_closed_invalid_join_code(client):
    teacher = make_admin("dash_scope_teacher", "secret")
    db.session.add(teacher)
    db.session.flush()

    profile_scope = IdentityProfile(profile_type='student', first_name='Scope', last_name='Q')
    db.session.add(profile_scope)
    db.session.flush()
    student = Student(identity_profile=profile_scope, block="A", salt=b"salt", has_completed_setup=True)
    db.session.add(student)
    db.session.flush()

    create_class_scope(
        teacher=teacher,
        join_code="SCOPEA1",
        student=student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    create_class_scope(
        teacher=teacher,
        join_code="SCOPEB1",
        student=student,
        block="B",
        display_name="B",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    _login_student(client, student.id, "MISSING")

    response = client.get("/student/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student/select-class-context")
    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "MISSING"
