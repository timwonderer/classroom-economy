"""
Default issue categories for the Issue Resolution System.

Categories guide students to provide relevant context for their issues.
"""

from app.extensions import db
from app.models import IssueCategory
from app.feats.base import requires_feat_context


DEFAULT_TRANSACTION_CATEGORIES = [
    {
        'name': 'Incorrect Amount',
        'description': 'The transaction amount is wrong',
        'category_type': 'transaction',
        'display_order': 1
    },
    {
        'name': 'Duplicate Transaction',
        'description': 'This transaction appears twice',
        'category_type': 'transaction',
        'display_order': 2
    },
    {
        'name': 'Wrong Account',
        'description': 'Transaction went to wrong account (checking vs savings)',
        'category_type': 'transaction',
        'display_order': 3
    },
    {
        'name': 'Timing Issue',
        'description': 'Transaction happened at wrong time or date',
        'category_type': 'transaction',
        'display_order': 4
    },
    {
        'name': 'Incorrect Charge/Fee',
        'description': 'I was charged incorrectly',
        'category_type': 'transaction',
        'display_order': 5
    },
    {
        'name': 'Missing Payment',
        'description': 'I should have been paid but wasn\'t',
        'category_type': 'transaction',
        'display_order': 6
    },
]

DEFAULT_GENERAL_CATEGORIES = [
    {
        'name': 'Clock In/Out Not Working',
        'description': 'Unable to clock in or clock out',
        'category_type': 'general',
        'display_order': 1
    },
    {
        'name': 'Balance Incorrect',
        'description': 'My balance doesn\'t make sense',
        'category_type': 'general',
        'display_order': 2
    },
    {
        'name': 'Feature Not Working',
        'description': 'Something on the site isn\'t working',
        'category_type': 'general',
        'display_order': 3
    },
    {
        'name': 'Cannot Purchase Item',
        'description': 'Unable to buy from store',
        'category_type': 'general',
        'display_order': 4
    },
    {
        'name': 'Missing Job/Assignment',
        'description': 'My job disappeared or changed',
        'category_type': 'general',
        'display_order': 5
    },
    {
        'name': 'Other Issue',
        'description': 'Something else is wrong',
        'category_type': 'general',
        'display_order': 99
    },
]


@requires_feat_context("FEAT-SUP-001")
def init_default_categories():
    """
    Initialize default issue categories in the database.
    Safe to run multiple times - will not create duplicates.

    Returns:
        int: Number of categories created
    """
    created_count = 0

    all_categories = DEFAULT_TRANSACTION_CATEGORIES + DEFAULT_GENERAL_CATEGORIES

    for cat_data in all_categories:
        # Check if category already exists
        existing = IssueCategory.query.filter_by(name=cat_data['name']).first()

        if not existing:
            category = IssueCategory(
                name=cat_data['name'],
                description=cat_data['description'],
                category_type=cat_data['category_type'],
                display_order=cat_data['display_order'],
                is_active=True
            )
            db.session.add(category)
            created_count += 1

    if created_count > 0:
        db.session.flush()  # FEAT-AUTHORIZED-SHELL

    return created_count


def get_active_categories(category_type=None):
    """
    Get active issue categories, optionally filtered by type.

    Args:
        category_type: Optional filter ('transaction', 'general', or None for all)

    Returns:
        List of (id, name) tuples suitable for SelectField choices
    """
    query = IssueCategory.query.filter_by(is_active=True)

    if category_type:
        query = query.filter_by(category_type=category_type)

    categories = query.order_by(IssueCategory.display_order).all()

    return [(cat.id, cat.name) for cat in categories]
