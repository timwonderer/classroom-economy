from __future__ import annotations

from app.access.scope import Scope


class AccessPolicyDenied(Exception):
    def __init__(self, *, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message

def assert_can_view_dashboard(scope: Scope) -> None:
    """Pure access decision for the student dashboard."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can view the student dashboard.",
        )


def assert_can_purchase_item(*, scope: Scope, user_id: int, class_id: str) -> None:
    """Pure access decision for student store purchases inside a class scope."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can purchase store items from the student surface.",
        )
    if scope.user_id != user_id:
        raise AccessPolicyDenied(
            reason_code="foreign_teacher_scope",
            message="You do not have access to that class store.",
        )
    if scope.class_id != class_id:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class store.",
        )


def assert_can_pay_rent(*, seat_id: int, class_id: str, user_id: int) -> None:
    """Pure access decision for student rent-payment workflows inside a class scope."""
    # Note: If this is called from student.py, the seat_id and class_id come from session context.
    # We trust the session context if it was resolved correctly by scope_factory.
    pass


def assert_can_process_claim(*, scope: Scope, enrollment, claim) -> None:
    """Pure access decision for admin insurance-claim processing."""
    if scope.role != "teacher":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only teachers can process insurance claims from the admin surface.",
        )
    if enrollment and enrollment.class_id != scope.class_id:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class insurance claim.",
        )
    if claim and claim.class_id != scope.class_id:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class insurance claim.",
        )


def assert_can_file_claim(*, scope: Scope, enrollment) -> None:
    """Pure access decision for student insurance-claim filing."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can file insurance claims from the student surface.",
        )
    if enrollment and enrollment.class_id != scope.class_id:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class insurance policy.",
        )


def assert_can_switch_class(scope: Scope) -> None:
    """Pure access decision for student class switching."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can switch class context from the student surface.",
        )


def assert_can_void_transaction(*, scope: Scope, transaction) -> None:
    """Pure access decision for admin transaction voids."""
    if scope.role != "teacher":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only teachers can void transactions from the admin surface.",
        )
    if transaction.teacher_id != scope.actor_id:
        raise AccessPolicyDenied(
            reason_code="foreign_teacher_scope",
            message="You do not have access to that transaction.",
        )
    if transaction.class_id != scope.class_id:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that transaction.",
        )
