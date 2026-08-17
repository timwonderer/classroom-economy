from __future__ import annotations
from typing import List, Optional
from app.extensions import db
from app.feats.base import requires_feat_context
from app.services.hall_pass_service import grant_hall_passes, revoke_hall_passes, get_hall_pass_balance

@requires_feat_context("FEAT-STOR-001")
def execute_bulk_adjust_hall_pass_entitlements(
    students: list,
    update_type: str,
    value: int,
    user_id: int
) -> tuple[list, list]:
    errors = []
    updated = []
    
    for student in students:
        try:
            if update_type == 'add':
                grant_hall_passes(
                    student.id,
                    student.class_id,
                    user_id,
                    "Admin bulk adjustment",
                    value,
                )
            elif update_type == 'remove':
                revoke_hall_passes(
                    student.id,
                    student.class_id,
                    user_id,
                    "Admin bulk adjustment",
                    value,
                )
        except ValueError as exc:
            errors.append(f"Student {student.id}: {exc}")
            continue

        updated.append(student.identity_profile.full_name if student.identity_profile else str(student.id))
        
    return updated, errors
