#!/usr/bin/env python3
"""
Fix remaining endpoint references with parameters that the first script missed.
"""

import re
from pathlib import Path

# Mapping of old endpoint names to new blueprint-namespaced names
ENDPOINT_MAPPINGS = {
    # Student routes
    'student_file_claim': 'student.file_claim',
    'student_view_policy': 'student.view_policy',
    'student_cancel_insurance': 'student.cancel_insurance',
    'student_purchase_insurance': 'student.purchase_insurance',
    'student_rent_pay': 'student.rent_pay',

    # Admin routes
    'void_transaction': 'admin.void_transaction',
    'set_hall_passes': 'admin.set_hall_passes',
    'student_detail': 'admin.student_detail',
    'admin_edit_store_item': 'admin.edit_store_item',
    'admin_edit_insurance_policy': 'admin.edit_insurance_policy',
    'admin_process_claim': 'admin.process_claim',
    'admin_view_student_policy': 'admin.view_student_policy',

    # System admin routes
    'system_admin_error_logs': 'sysadmin.error_logs',
    'system_admin_delete_admin': 'sysadmin.delete_admin',
}


def fix_template_file(filepath):
    """Fix endpoint references with parameters in a single template file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    changes_made = []

    for old_endpoint, new_endpoint in ENDPOINT_MAPPINGS.items():
        # Match url_for('old_endpoint', with any parameters after
        # This handles cases like url_for('student_detail', student_id=student.id)
        patterns = [
            (rf"url_for\('{old_endpoint}'", f"url_for('{new_endpoint}'"),
            (rf'url_for\("{old_endpoint}"', f'url_for("{new_endpoint}"'),
        ]

        for old_pattern, new_pattern in patterns:
            matches = re.findall(old_pattern, content)
            if matches:
                count = len(matches)
                content = re.sub(old_pattern, new_pattern, content)
                changes_made.append(f"  {old_endpoint} -> {new_endpoint} ({count} occurrence(s))")

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

    print("🔧 Fixing remaining template endpoint references with parameters...")
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
        matches = re.findall(r"url_for\(['\"]([^.'\"]+)['\"]", content)
        for match in matches:
            if match != 'static' and '<!--' not in content[max(0, content.find(match)-50):content.find(match)]:
                remaining_broken.append(f"{template_file.name}: url_for('{match}')")

    if remaining_broken:
        print(f"\n⚠️  Found {len(remaining_broken)} potentially broken references:")
        for ref in remaining_broken[:20]:  # Show first 20
            print(f"   {ref}")
        if len(remaining_broken) > 20:
            print(f"   ... and {len(remaining_broken) - 20} more")
    else:
        print("✅ No broken references found!")

    print("\n✅ Template fixing complete!")
    return 0


if __name__ == '__main__':
    exit(main())
