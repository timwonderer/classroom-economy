#!/usr/bin/env python3
"""One-time prompt for teachers to upgrade legacy insurance policies.

This script flags teachers who still have legacy insurance policies so the
admin dashboard can display a prompt directing them to the new tiered design.

Usage:
    python scripts/prompt_insurance_tier_upgrade.py

Run from the repository root so Flask can resolve the application package.
"""

from typing import List

from sqlalchemy import and_
from sqlalchemy.orm.attributes import flag_modified

from app import create_app, db
from app.models import InsurancePolicy, TeacherOnboarding


LEGACY_POLICY_FILTER = and_(
    InsurancePolicy.tier_category_id.is_(None),
    InsurancePolicy.tier_level.is_(None),
)


def get_teachers_with_legacy_policies() -> List[int]:
    """Return teacher IDs that still have legacy (untiered) insurance policies."""

    teachers = (
        db.session.query(InsurancePolicy.teacher_id)
        .filter(InsurancePolicy.teacher_id.isnot(None))
        .filter(LEGACY_POLICY_FILTER)
        .distinct()
        .all()
    )
    return [teacher_id for (teacher_id,) in teachers]


def ensure_onboarding_record(teacher_id: int) -> TeacherOnboarding:
    """Fetch or create an onboarding record for the teacher."""

    onboarding = TeacherOnboarding.query.filter_by(teacher_id=teacher_id).first()
    if not onboarding:
        onboarding = TeacherOnboarding(teacher_id=teacher_id, steps_completed={})
        db.session.add(onboarding)
        db.session.flush()

    if onboarding.steps_completed is None:
        onboarding.steps_completed = {}

    return onboarding


def flag_teachers_for_prompt(teacher_ids: List[int]) -> int:
    """Set the prompt flag for each teacher and return the count updated."""

    updated = 0
    for teacher_id in teacher_ids:
        onboarding = ensure_onboarding_record(teacher_id)
        already_flagged = onboarding.steps_completed.get("needs_insurance_tier_upgrade")

        onboarding.steps_completed["needs_insurance_tier_upgrade"] = True
        flag_modified(onboarding, "steps_completed")
        updated += 1 if not already_flagged else 0

    db.session.commit()
    return updated


def main():
    app = create_app()
    with app.app_context():
        teacher_ids = get_teachers_with_legacy_policies()
        if not teacher_ids:
            print("No teachers with legacy insurance policies found. No action taken.")
            return

        newly_flagged = flag_teachers_for_prompt(teacher_ids)

        print(
            f"Flagged {newly_flagged} teacher(s) for insurance tier upgrade prompt "
            f"({len(teacher_ids)} total with legacy policies)."
        )


if __name__ == "__main__":
    main()
