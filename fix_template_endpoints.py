#!/usr/bin/env python3
"""
Script to fix all broken endpoint references in Jinja2 templates.

After the blueprint refactoring, all endpoint names changed from simple names
(e.g., 'student_dashboard') to blueprint-namespaced names (e.g., 'student.dashboard').

This script systematically updates all url_for() calls in template files.
"""

import os
import re
from pathlib import Path

# Mapping of old endpoint names to new blueprint-namespaced names
ENDPOINT_MAPPINGS = {
    # Student routes
    'student_dashboard': 'student.dashboard',
    'student_login': 'student.login',
    'student_logout': 'student.logout',
    'student_claim_account': 'student.claim_account',
    'student_create_username': 'student.create_username',
    'student_setup_pin_passphrase': 'student.setup_pin_passphrase',
    'student_transfer': 'student.transfer',
    'student_insurance': 'student.student_insurance',
    'student_shop': 'student.shop',
    'student_rent': 'student.rent',
    'student_file_claim': 'student.file_claim',
    'student_view_policy': 'student.view_policy',

    # Admin routes
    'admin_dashboard': 'admin.dashboard',
    'admin_login': 'admin.login',
    'admin_logout': 'admin.logout',
    'admin_signup': 'admin.signup',
    'admin_students': 'admin.students',
    'admin_student_detail': 'admin.student_detail',
    'admin_store_management': 'admin.store_management',
    'admin_edit_store_item': 'admin.edit_store_item',
    'admin_delete_store_item': 'admin.delete_store_item',
    'admin_insurance_management': 'admin.insurance_management',
    'admin_edit_insurance_policy': 'admin.edit_insurance_policy',
    'admin_deactivate_insurance_policy': 'admin.deactivate_insurance_policy',
    'admin_view_student_policy': 'admin.view_student_policy',
    'admin_process_claim': 'admin.process_claim',
    'admin_payroll': 'admin.payroll',
    'admin_payroll_history': 'admin.payroll_history',
    'admin_payroll_settings': 'admin.payroll_settings',
    'admin_payroll_add_reward': 'admin.payroll_add_reward',
    'admin_payroll_add_fine': 'admin.payroll_add_fine',
    'admin_payroll_delete_reward': 'admin.payroll_delete_reward',
    'admin_payroll_delete_fine': 'admin.payroll_delete_fine',
    'admin_payroll_edit_reward': 'admin.payroll_edit_reward',
    'admin_payroll_edit_fine': 'admin.payroll_edit_fine',
    'admin_payroll_apply_reward': 'admin.payroll_apply_reward',
    'admin_payroll_apply_fine': 'admin.payroll_apply_fine',
    'admin_payroll_manual_payment': 'admin.payroll_manual_payment',
    'admin_void_payroll_transaction': 'admin.void_payroll_transaction',
    'admin_void_transactions_bulk': 'admin.void_transactions_bulk',
    'admin_transactions': 'admin.transactions',
    'admin_void_transaction': 'admin.void_transaction',
    'admin_attendance_log': 'admin.attendance_log',
    'admin_hall_pass': 'admin.hall_pass',
    'admin_rent_settings': 'admin.rent_settings',
    'admin_upload_students': 'admin.upload_students',
    'admin_give_bonus_all': 'admin.give_bonus_all',
    'admin_run_payroll': 'admin.run_payroll',
    'download_csv_template': 'admin.download_csv_template',
    'export_students': 'admin.export_students',
    'set_hall_passes': 'admin.set_hall_passes',

    # System admin routes
    'system_admin_dashboard': 'sysadmin.dashboard',
    'system_admin_login': 'sysadmin.login',
    'system_admin_logout': 'sysadmin.logout',
    'system_admin_logs': 'sysadmin.logs',
    'system_admin_error_logs': 'sysadmin.error_logs',
    'system_admin_logs_testing': 'sysadmin.logs_testing',
    'system_admin_manage_admins': 'sysadmin.manage_admins',
    'system_admin_delete_admin': 'sysadmin.delete_admin',
    'system_admin_manage_teachers': 'sysadmin.manage_teachers',
    'system_admin_delete_teacher': 'sysadmin.delete_teacher',
    'test_error_400': 'sysadmin.test_error_400',
    'test_error_401': 'sysadmin.test_error_401',
    'test_error_403': 'sysadmin.test_error_403',
    'test_error_404': 'sysadmin.test_error_404',
    'test_error_500': 'sysadmin.test_error_500',
    'test_error_503': 'sysadmin.test_error_503',

    # Main routes
    'privacy': 'main.privacy',
    'terms': 'main.terms',
    'home': 'main.home',
    'health_check': 'main.health_check',
    'hall_pass_terminal': 'main.hall_pass_terminal',
    'hall_pass_verification': 'main.hall_pass_verification',

    # API routes (less common in templates but include for completeness)
    'handle_tap': 'api.handle_tap',
    'student_status': 'api.student_status',
    'purchase_item': 'api.purchase_item',
    'use_item': 'api.use_item',
    'approve_redemption': 'api.approve_redemption',
}


def fix_template_file(filepath):
    """Fix endpoint references in a single template file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    changes_made = []

    # Fix url_for() calls
    for old_endpoint, new_endpoint in ENDPOINT_MAPPINGS.items():
        # Match url_for('old_endpoint') or url_for("old_endpoint")
        patterns = [
            (f"url_for('{old_endpoint}')", f"url_for('{new_endpoint}')"),
            (f'url_for("{old_endpoint}")', f'url_for("{new_endpoint}")'),
        ]

        for old_pattern, new_pattern in patterns:
            if old_pattern in content:
                count = content.count(old_pattern)
                content = content.replace(old_pattern, new_pattern)
                changes_made.append(f"  {old_endpoint} -> {new_endpoint} ({count} occurrence(s))")

    # Check for request.endpoint comparisons (e.g., in active nav highlighting)
    for old_endpoint, new_endpoint in ENDPOINT_MAPPINGS.items():
        # Match request.endpoint == 'old_endpoint'
        patterns = [
            (f"request.endpoint == '{old_endpoint}'", f"request.endpoint == '{new_endpoint}'"),
            (f'request.endpoint == "{old_endpoint}"', f'request.endpoint == "{new_endpoint}"'),
        ]

        for old_pattern, new_pattern in patterns:
            if old_pattern in content:
                count = content.count(old_pattern)
                content = content.replace(old_pattern, new_pattern)
                changes_made.append(f"  request.endpoint check: {old_endpoint} -> {new_endpoint} ({count} occurrence(s))")

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, changes_made

    return False, []


def main():
    """Main function to process all template files."""
    templates_dir = Path('templates')

    if not templates_dir.exists():
        print("❌ templates/ directory not found")
        return 1

    print("🔧 Fixing template endpoint references...")
    print("=" * 70)

    total_files = 0
    fixed_files = 0
    total_changes = 0

    # Process all .html files in templates/
    for template_file in sorted(templates_dir.glob('*.html')):
        total_files += 1
        modified, changes = fix_template_file(template_file)

        if modified:
            fixed_files += 1
            total_changes += len(changes)
            print(f"\n✅ Fixed: {template_file.name}")
            for change in changes:
                print(change)

    print("\n" + "=" * 70)
    print(f"📊 Summary:")
    print(f"   Total template files: {total_files}")
    print(f"   Files modified: {fixed_files}")
    print(f"   Total changes: {total_changes}")

    # Check for remaining broken references
    print("\n🔍 Checking for remaining broken references...")
    remaining_broken = []

    for template_file in templates_dir.glob('*.html'):
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find url_for calls without dots (not blueprint-namespaced)
        # But exclude 'static' which is valid
        matches = re.findall(r"url_for\(['\"]([^.'\"]+)['\"]\)", content)
        for match in matches:
            if match != 'static':
                remaining_broken.append(f"{template_file.name}: url_for('{match}')")

    if remaining_broken:
        print(f"\n⚠️  Found {len(remaining_broken)} potentially broken references:")
        for ref in remaining_broken[:10]:  # Show first 10
            print(f"   {ref}")
        if len(remaining_broken) > 10:
            print(f"   ... and {len(remaining_broken) - 10} more")
    else:
        print("✅ No broken references found!")

    print("\n✅ Template fixing complete!")
    return 0


if __name__ == '__main__':
    exit(main())
