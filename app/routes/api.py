"""
API routes for Classroom Token Hub.

RESTful JSON API endpoints for student transactions, hall passes, attendance,
and other interactive features. Most routes require authentication.
"""

import random
import string
import re
import pytz
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import check_password_hash

from app.extensions import db, limiter
from app.models import (
    Student, StoreItem, StudentItem, Transaction, TapEvent,
    HallPassLog, HallPassSettings, InsuranceClaim, BankingSettings,
    StudentTeacher, TeacherBlock
)
from app.auth import login_required, admin_required, get_logged_in_student, get_current_admin, SESSION_TIMEOUT_MINUTES
from app.routes.student import get_current_teacher_id

# Import external modules
from attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    get_all_block_statuses,
    get_join_code_for_student_period
)
from payroll import get_pay_rate_for_block

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


# -------------------- STORE API --------------------

def _charge_overdraft_fee_if_needed(student, banking_settings):
    """
    Check if student's checking balance is negative and charge overdraft fee if enabled.
    Returns (fee_charged, fee_amount) tuple.
    """
    if not banking_settings or not banking_settings.overdraft_fee_enabled:
        return False, 0.0

    # Only charge if balance is negative
    if student.checking_balance >= 0:
        return False, 0.0

    fee_amount = 0.0

    if banking_settings.overdraft_fee_type == 'flat':
        fee_amount = banking_settings.overdraft_fee_flat_amount
    elif banking_settings.overdraft_fee_type == 'progressive':
        # Count how many overdraft fees charged this month
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        overdraft_fee_count = Transaction.query.filter(
            Transaction.student_id == student.id,
            Transaction.type == 'overdraft_fee',
            Transaction.timestamp >= month_start
        ).count()

        # Determine which tier to use (1st, 2nd, 3rd, or cap)
        if overdraft_fee_count == 0:
            fee_amount = banking_settings.overdraft_fee_progressive_1 or 0.0
        elif overdraft_fee_count == 1:
            fee_amount = banking_settings.overdraft_fee_progressive_2 or 0.0
        elif overdraft_fee_count >= 2:
            fee_amount = banking_settings.overdraft_fee_progressive_3 or 0.0

        # Check if cap is exceeded
        if banking_settings.overdraft_fee_progressive_cap:
            total_fees_this_month = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.student_id == student.id,
                Transaction.type == 'overdraft_fee',
                Transaction.timestamp >= month_start
            ).scalar() or 0.0

            # total_fees_this_month is negative, so we negate it
            if abs(total_fees_this_month) + fee_amount > banking_settings.overdraft_fee_progressive_cap:
                # Don't charge more than the cap
                fee_amount = max(0, banking_settings.overdraft_fee_progressive_cap - abs(total_fees_this_month))

    if fee_amount > 0:
        # Charge the fee
        overdraft_fee_tx = Transaction(
            student_id=student.id,
            amount=-fee_amount,
            account_type='checking',
            type='overdraft_fee',
            description=f'Overdraft fee (balance: ${student.checking_balance:.2f})'
        )
        db.session.add(overdraft_fee_tx)
        db.session.flush()  # Update the balance calculation
        return True, fee_amount

    return False, 0.0


@api_bp.route('/purchase-item', methods=['POST'])
@login_required
def purchase_item():
    from app.routes.student import get_current_class_context

    student = get_logged_in_student()
    data = request.get_json()
    item_id = data.get('item_id')
    passphrase = data.get('passphrase')
    quantity = int(data.get('quantity', 1))  # Default to 1 if not specified

    if not all([item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    if quantity < 1:
        return jsonify({"status": "error", "message": "Quantity must be at least 1."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # CRITICAL FIX v2: Get full class context (join_code is source of truth)
    context = get_current_class_context()
    if not context:
        return jsonify({"status": "error", "message": "No class context available."}), 400

    join_code = context['join_code']
    teacher_id = context['teacher_id']

    item = StoreItem.query.filter_by(id=item_id, teacher_id=teacher_id).first()

    # 2. Validate item and purchase conditions
    if not item or not item.is_active:
        return jsonify({"status": "error", "message": "This item is not available."}), 404

    # Calculate price (with bulk discount if applicable)
    unit_price = item.price
    if (item.bulk_discount_enabled and
        item.bulk_discount_quantity is not None and
        item.bulk_discount_percentage is not None and
        quantity >= item.bulk_discount_quantity):
        discount_multiplier = 1 - (item.bulk_discount_percentage / 100)
        unit_price = item.price * discount_multiplier

    total_price = unit_price * quantity

    # Get banking settings for overdraft handling (reuse teacher_id from above)
    banking_settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first()

    # Check if student has sufficient funds
    if student.checking_balance < total_price:
        # Check if overdraft protection is enabled (savings can cover the difference)
        if banking_settings and banking_settings.overdraft_protection_enabled:
            shortfall = total_price - student.checking_balance
            if student.savings_balance >= shortfall:
                # Allow transaction - overdraft protection will transfer from savings
                pass
            else:
                return jsonify({"status": "error", "message": f"Insufficient funds in both checking and savings. You need ${total_price:.2f} total but have ${student.checking_balance + student.savings_balance:.2f}."}), 400
        # Check if overdraft fees are enabled (allows negative balance)
        elif banking_settings and banking_settings.overdraft_fee_enabled:
            # Allow transaction - will charge overdraft fee after transaction
            pass
        else:
            # No overdraft options - reject transaction
            return jsonify({"status": "error", "message": f"Insufficient funds. You need ${total_price:.2f} but have ${student.checking_balance:.2f}."}), 400

    if item.inventory is not None and item.inventory < quantity:
        return jsonify({"status": "error", "message": f"Insufficient stock. Only {item.inventory} available."}), 400

    if item.limit_per_student is not None:
        if item.item_type == 'hall_pass':
            # For hall passes, check transaction history and sum quantities
            # Description format: "Purchase: {name}" or "Purchase: {name} (xN)" or "Purchase: {name} (xN) [discount]"
            transactions = Transaction.query.filter(
                Transaction.student_id == student.id,
                Transaction.type == 'purchase',
                Transaction.description.like(f"Purchase: {item.name}%")
            ).all()

            # Parse quantities from transaction descriptions
            total_purchased = 0
            for txn in transactions:
                # Extract quantity from description (e.g., "(x3)" -> 3)
                match = re.search(r'\(x(\d+)\)', txn.description)
                if match:
                    total_purchased += int(match.group(1))
                else:
                    # No quantity suffix means quantity was 1
                    total_purchased += 1

            purchase_count = total_purchased
        else:
            purchase_count = StudentItem.query.filter_by(student_id=student.id, store_item_id=item.id).count()
        if purchase_count + quantity > item.limit_per_student:
            return jsonify({"status": "error", "message": f"You can only purchase {item.limit_per_student - purchase_count} more of this item."}), 400

    # 3. Process the transaction
    try:
        # Deduct from checking account
        purchase_description = f"Purchase: {item.name}"
        if quantity > 1:
            purchase_description += f" (x{quantity})"
        if item.bulk_discount_enabled and quantity >= item.bulk_discount_quantity:
            purchase_description += f" [{item.bulk_discount_percentage}% bulk discount]"

        # CRITICAL FIX v2: Add join_code to purchase transaction
        purchase_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,  # CRITICAL: Add join_code for period isolation
            amount=-total_price,
            account_type='checking',
            type='purchase',
            description=purchase_description
        )
        db.session.add(purchase_tx)

        # Handle inventory
        if item.inventory is not None:
            item.inventory -= quantity

        # --- Handle special item type: Hall Pass ---
        if item.item_type == 'hall_pass':
            student.hall_passes += quantity  # Add all purchased hall passes
            db.session.flush()  # Flush to update balances without committing yet

            # Check if overdraft protection should transfer funds from savings
            if banking_settings and banking_settings.overdraft_protection_enabled and student.checking_balance < 0:
                shortfall = abs(student.checking_balance)
                if student.savings_balance >= shortfall:
                    # CRITICAL FIX v2: Transfer from savings to checking with join_code
                    transfer_tx_withdraw = Transaction(
                        student_id=student.id,
                        teacher_id=teacher_id,
                        join_code=join_code,  # CRITICAL: Add join_code for period isolation
                        amount=-shortfall,
                        account_type='savings',
                        type='Withdrawal',
                        description='Overdraft protection transfer to checking'
                    )
                    transfer_tx_deposit = Transaction(
                        student_id=student.id,
                        teacher_id=teacher_id,
                        join_code=join_code,  # CRITICAL: Add join_code for period isolation
                        amount=shortfall,
                        account_type='checking',
                        type='Deposit',
                        description='Overdraft protection transfer from savings'
                    )
                    db.session.add(transfer_tx_withdraw)
                    db.session.add(transfer_tx_deposit)
                    db.session.flush()  # Flush to update balances

            # Check if overdraft fee should be charged (after overdraft protection)
            fee_charged, fee_amount = _charge_overdraft_fee_if_needed(student, banking_settings)

            # Commit all transactions together
            db.session.commit()

            return jsonify({"status": "success", "message": f"You purchased {quantity} Hall Pass(es)! Your new balance is {student.hall_passes}."})

        # --- Standard Item Logic ---
        # Create the student's item(s)
        expiry_date = None
        if item.item_type == 'delayed' and item.auto_expiry_days:
            expiry_date = datetime.now(timezone.utc) + timedelta(days=item.auto_expiry_days)

        student_item_status = 'purchased'
        if item.item_type == 'immediate':
            student_item_status = 'redeemed' # Immediate use items are redeemed instantly
        elif item.item_type == 'collective':
            student_item_status = 'pending'
        else: # delayed
            student_item_status = 'purchased'

        # Handle bundle items - create one StudentItem with bundle tracking
        if item.is_bundle and item.bundle_quantity is not None:
            new_student_item = StudentItem(
                student_id=student.id,
                store_item_id=item.id,
                purchase_date=datetime.now(timezone.utc),
                expiry_date=expiry_date,
                status=student_item_status,
                is_from_bundle=True,
                bundle_remaining=item.bundle_quantity * quantity,  # Total uses = bundle_quantity * number of bundles purchased
                quantity_purchased=quantity
            )
            db.session.add(new_student_item)
        elif item.is_bundle and item.bundle_quantity is None:
            # Safety: if bundle is enabled but quantity is missing, treat as regular item
            current_app.logger.error(f"Bundle item {item.id} has is_bundle=True but bundle_quantity=None. Treating as regular item.")
            new_student_item = StudentItem(
                student_id=student.id,
                store_item_id=item.id,
                purchase_date=datetime.now(timezone.utc),
                expiry_date=expiry_date,
                status=student_item_status,
                is_from_bundle=False,
                quantity_purchased=quantity
            )
            db.session.add(new_student_item)
        else:
            # For non-bundle items, create separate StudentItem records for each quantity
            for _ in range(quantity):
                new_student_item = StudentItem(
                    student_id=student.id,
                    store_item_id=item.id,
                    purchase_date=datetime.now(timezone.utc),
                    expiry_date=expiry_date,
                    status=student_item_status,
                    is_from_bundle=False,
                    quantity_purchased=1
                )
                db.session.add(new_student_item)

        db.session.flush()  # Flush to update balances without committing yet

        # Handle overdraft protection and fees for regular items
        # Check if overdraft protection should transfer funds from savings
        if banking_settings and banking_settings.overdraft_protection_enabled and student.checking_balance < 0:
            shortfall = abs(student.checking_balance)
            if student.savings_balance >= shortfall:
                # CRITICAL FIX v2: Transfer from savings to checking with join_code
                transfer_tx_withdraw = Transaction(
                    student_id=student.id,
                    teacher_id=teacher_id,
                    join_code=join_code,  # CRITICAL: Add join_code for period isolation
                    amount=-shortfall,
                    account_type='savings',
                    type='Withdrawal',
                    description='Overdraft protection transfer to checking'
                )
                transfer_tx_deposit = Transaction(
                    student_id=student.id,
                    teacher_id=teacher_id,
                    join_code=join_code,  # CRITICAL: Add join_code for period isolation
                    amount=shortfall,
                    account_type='checking',
                    type='Deposit',
                    description='Overdraft protection transfer from savings'
                )
                db.session.add(transfer_tx_withdraw)
                db.session.add(transfer_tx_deposit)
                db.session.flush()  # Flush to update balances

        # Check if overdraft fee should be charged (after overdraft protection)
        fee_charged, fee_amount = _charge_overdraft_fee_if_needed(student, banking_settings)

        # --- Collective Item Logic ---
        if item.item_type == 'collective':
            # Check if all students in the same block have purchased this item
            students_in_block = Student.query.filter_by(block=student.block).all()
            student_ids_in_block = {s.id for s in students_in_block}

            purchased_students_count = db.session.query(func.count(func.distinct(StudentItem.student_id))).filter(
                StudentItem.store_item_id == item.id,
                StudentItem.student_id.in_(student_ids_in_block)
            ).scalar()

            if purchased_students_count >= len(student_ids_in_block):
                # Threshold met, update all pending items for this collective goal to processing
                StudentItem.query.filter(
                    StudentItem.store_item_id == item.id,
                    StudentItem.status == 'pending'
                ).update({"status": "processing"})
                # This flash won't be seen by the user due to the JSON response,
                # but it's good for logging/debugging. A more robust solution might use websockets.
                current_app.logger.info(f"Collective goal '{item.name}' for block {student.block} has been met!")

        # Commit purchases for both collective and non-collective items
        db.session.commit()

        # Build success message
        success_message = f"You purchased {item.name}!"
        if item.is_bundle and item.bundle_quantity is not None:
            total_uses = item.bundle_quantity * quantity
            success_message = f"You purchased {quantity} bundle(s) of {item.name}! You have {total_uses} uses."
        elif quantity > 1:
            success_message = f"You purchased {quantity}x {item.name}!"

        if (item.bulk_discount_enabled and
            item.bulk_discount_quantity is not None and
            item.bulk_discount_percentage is not None and
            quantity >= item.bulk_discount_quantity):
            success_message += f" (Saved {item.bulk_discount_percentage}% with bulk discount!)"

        return jsonify({"status": "success", "message": success_message})

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Purchase failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred during purchase. Please try again."}), 500


@api_bp.route('/use-item', methods=['POST'])
@login_required
def use_item():
    student = get_logged_in_student()
    data = request.get_json()
    student_item_id = data.get('student_item_id')
    passphrase = data.get('passphrase')
    details = data.get('redemption_details', data.get('details', ''))  # optional notes from student

    if not all([student_item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # 2. Get the student's item
    student_item = StudentItem.query.get(student_item_id)

    if not student_item or student_item.student_id != student.id:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Validate the item can be used
    if student_item.is_from_bundle:
        # For bundle items, check bundle_remaining
        if student_item.bundle_remaining is None or student_item.bundle_remaining <= 0:
            return jsonify({"status": "error", "message": "All uses from this bundle have been consumed."}), 400
    else:
        # For regular items, check status
        if student_item.status not in ['purchased', 'pending']:
            return jsonify({"status": "error", "message": "This item has already been used or is not available."}), 400

    # Check expiry
    if student_item.expiry_date and datetime.now(timezone.utc) > student_item.expiry_date:
        student_item.status = 'expired'
        db.session.commit()
        return jsonify({"status": "error", "message": "This item has expired."}), 400

    # 3. Mark as processing and create redemption transaction
    try:
        # Handle bundle items differently
        if student_item.is_from_bundle:
            # Decrement bundle_remaining
            student_item.bundle_remaining -= 1
            if student_item.bundle_remaining == 0:
                student_item.status = 'redeemed'  # All uses consumed
            student_item.redemption_date = datetime.now(timezone.utc)
            if student_item.redemption_details:
                student_item.redemption_details += f"\n---\n{details}"
            else:
                student_item.redemption_details = details
        else:
            # Regular item - mark as processing
            student_item.status = 'processing'
            student_item.redemption_date = datetime.now(timezone.utc)
            student_item.redemption_details = details

        # CRITICAL FIX v2: Create a redemption transaction with join_code
        # This is a $0 transaction to log the redemption event
        # Get context from current session
        from app.routes.student import get_current_class_context
        context = get_current_class_context()

        if context:
            redemption_tx = Transaction(
                student_id=student.id,
                teacher_id=context['teacher_id'],
                join_code=context['join_code'],  # CRITICAL: Add join_code for period isolation
                amount=0.0,
                account_type='checking',
                type='redemption',
                description=f"Used: {student_item.store_item.name}" + (f" (bundle: {student_item.bundle_remaining} remaining)" if student_item.is_from_bundle else "")
            )
            db.session.add(redemption_tx)
        db.session.commit()

        if student_item.is_from_bundle:
            return jsonify({"status": "success", "message": f"You have used 1 from your bundle of {student_item.store_item.name}. {student_item.bundle_remaining} uses remaining."})
        else:
            return jsonify({"status": "success", "message": f"You have requested to use {student_item.store_item.name}. Awaiting admin approval."})

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Item use failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred. Please try again."}), 500


@api_bp.route('/approve-redemption', methods=['POST'])
@admin_required
def approve_redemption():
    data = request.get_json()
    student_item_id = data.get('student_item_id')

    student_item = StudentItem.query.get(student_item_id)
    if not student_item or student_item.status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    try:
        student_item.status = 'completed'

        # Find the corresponding 'redemption' transaction and update its description
        redemption_tx = Transaction.query.filter_by(
            student_id=student_item.student_id,
            type='redemption',
            description=f"Used: {student_item.store_item.name}"
        ).order_by(Transaction.timestamp.desc()).first()

        if redemption_tx:
            redemption_tx.description = f"Redeemed: {student_item.store_item.name}"

        db.session.commit()
        return jsonify({"status": "success", "message": "Redemption approved."})
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Redemption approval failed for student_item {student_item_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred."}), 500


# -------------------- HALL PASS API --------------------

@api_bp.route('/hall-pass/<int:pass_id>/<string:action>', methods=['POST'])
@admin_required
def handle_hall_pass_action(pass_id, action):
    log_entry = HallPassLog.query.get_or_404(pass_id)
    student = log_entry.student
    now = datetime.now(timezone.utc)

    if action == 'approve':
        if log_entry.status != 'pending':
            return jsonify({"status": "error", "message": "Pass is not pending."}), 400

        # Check if hall pass deduction is needed (not for Office/Summons/Done for the day)
        should_deduct = log_entry.reason.lower() not in ['office', 'summons', 'done for the day']

        if should_deduct and student.hall_passes <= 0:
            return jsonify({"status": "error", "message": "Student has no hall passes left."}), 400

        # Generate unique pass number (letter + 2 digits)
        while True:
            letter = random.choice(string.ascii_uppercase)
            digits = random.randint(10, 99)
            pass_number = f"{letter}{digits}"
            # Check if this pass number already exists
            existing = HallPassLog.query.filter_by(pass_number=pass_number).first()
            if not existing:
                break

        log_entry.status = 'approved'
        log_entry.decision_time = now
        log_entry.pass_number = pass_number

        # Only deduct hall pass for regular reasons (not Office/Summons/Done for the day)
        if should_deduct:
            student.hall_passes -= 1

        db.session.commit()
        return jsonify({"status": "success", "message": "Pass approved.", "pass_number": pass_number})

    elif action == 'reject':
        if log_entry.status != 'pending':
            return jsonify({"status": "error", "message": "Pass is not pending."}), 400

        log_entry.status = 'rejected'
        log_entry.decision_time = now
        db.session.commit()
        return jsonify({"status": "success", "message": "Pass rejected."})

    elif action == 'leave':
        if log_entry.status != 'approved':
            return jsonify({"status": "error", "message": "Pass is not approved."}), 400

        # Create a tap-out event for attendance tracking
        tap_out_event = TapEvent(
            student_id=student.id,
            period=log_entry.period,
            status='inactive',
            timestamp=now,
            reason=log_entry.reason,
            join_code=log_entry.join_code
        )
        log_entry.status = 'left'
        log_entry.left_time = now
        db.session.add(tap_out_event)
        db.session.commit()
        return jsonify({"status": "success", "message": "Student has left the class."})

    elif action == 'return':
        if log_entry.status != 'left':
            return jsonify({"status": "error", "message": "Student is not out of class."}), 400

        # Create a tap-in event to close the loop
        tap_in_event = TapEvent(
            student_id=student.id,
            period=log_entry.period,
            status='active',
            timestamp=now,
            reason="Return from hall pass",
            join_code=log_entry.join_code
        )
        log_entry.status = 'returned'
        log_entry.return_time = now
        db.session.add(tap_in_event)
        db.session.commit()
        return jsonify({"status": "success", "message": "Student has returned."})

    return jsonify({"status": "error", "message": "Invalid action."}), 400


@api_bp.route('/hall-pass/verification/active', methods=['GET'])
def get_active_hall_passes():
    """Get last 10 students who used hall passes for verification display"""
    # Get the last 10 students who have left class (both currently out and recently returned)
    # Ordered by left_time descending (most recent first)
    recent_passes = HallPassLog.query.filter(
        HallPassLog.status.in_(['left', 'returned']),
        HallPassLog.left_time.isnot(None)
    ).order_by(HallPassLog.left_time.desc()).limit(10).all()

    # Helper function to ensure times are marked as UTC
    def format_utc_time(dt):
        if not dt:
            return None
        # Ensure datetime is treated as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    passes_data = []
    for log_entry in recent_passes:
        student = log_entry.student
        passes_data.append({
            "student_name": student.full_name,
            "period": log_entry.period,
            "destination": log_entry.reason,
            "left_time": format_utc_time(log_entry.left_time),
            "return_time": format_utc_time(log_entry.return_time),
            "pass_number": log_entry.pass_number,
            "status": log_entry.status
        })

    return jsonify({
        "status": "success",
        "passes": passes_data
    })


@api_bp.route('/hall-pass/lookup/<string:pass_number>', methods=['GET'])
def lookup_hall_pass(pass_number):
    """Look up a hall pass by its pass number (for terminal use)"""
    # Find the hall pass log entry by pass number
    log_entry = HallPassLog.query.filter_by(pass_number=pass_number.upper()).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Pass number not found."}), 404

    student = log_entry.student

    # Return the pass information (ensure times are marked as UTC)
    def format_utc_time(dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    return jsonify({
        "status": "success",
        "pass": {
            "id": log_entry.id,
            "student_name": student.full_name,
            "period": log_entry.period,
            "destination": log_entry.reason,
            "pass_number": log_entry.pass_number,
            "pass_status": log_entry.status,
            "request_time": format_utc_time(log_entry.request_time),
            "decision_time": format_utc_time(log_entry.decision_time),
            "left_time": format_utc_time(log_entry.left_time),
            "return_time": format_utc_time(log_entry.return_time)
        }
    })


@api_bp.route('/hall-pass/terminal/use', methods=['POST'])
def hall_pass_terminal_use():
    """Mark a hall pass as 'left' when student scans at terminal"""
    data = request.get_json()
    pass_number = data.get('pass_number', '').strip().upper()

    if not pass_number:
        return jsonify({"status": "error", "message": "Pass number is required."}), 400

    log_entry = HallPassLog.query.filter_by(pass_number=pass_number).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Invalid pass number."}), 404

    if log_entry.status != 'approved':
        return jsonify({"status": "error", "message": f"Pass is not approved. Current status: {log_entry.status}"}), 400

    # Mark as left and create tap-out event
    now = datetime.now(timezone.utc)
    log_entry.status = 'left'
    log_entry.left_time = now

    # Create tap-out event for attendance tracking
    tap_out_event = TapEvent(
        student_id=log_entry.student_id,
        period=log_entry.period,
        status='inactive',
        timestamp=now,
        reason=log_entry.reason,
        join_code=log_entry.join_code
    )
    db.session.add(tap_out_event)

    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"{log_entry.student.full_name} has left for {log_entry.reason}.",
            "student_name": log_entry.student.full_name,
            "destination": log_entry.reason
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass terminal use failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/terminal/return', methods=['POST'])
def hall_pass_terminal_return():
    """Mark a hall pass as 'returned' when student scans back in at terminal"""
    data = request.get_json()
    pass_number = data.get('pass_number', '').strip().upper()

    if not pass_number:
        return jsonify({"status": "error", "message": "Pass number is required."}), 400

    log_entry = HallPassLog.query.filter_by(pass_number=pass_number).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Invalid pass number."}), 404

    if log_entry.status != 'left':
        return jsonify({"status": "error", "message": f"Student is not currently out. Status: {log_entry.status}"}), 400

    # Mark as returned and create tap-in event
    now = datetime.now(timezone.utc)
    log_entry.status = 'returned'
    log_entry.return_time = now

    # Create tap-in event for attendance tracking
    tap_in_event = TapEvent(
        student_id=log_entry.student_id,
        period=log_entry.period,
        status='active',
        timestamp=now,
        reason="Returned from hall pass",
        join_code=log_entry.join_code
    )
    db.session.add(tap_in_event)

    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"{log_entry.student.full_name} has returned.",
            "student_name": log_entry.student.full_name
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass terminal return failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/cancel/<int:pass_id>', methods=['POST'])
@login_required
def cancel_hall_pass(pass_id):
    """Allow students to cancel their pending hall pass request"""
    student = get_logged_in_student()
    log_entry = HallPassLog.query.get_or_404(pass_id)

    # Verify this pass belongs to the logged-in student
    if log_entry.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    # Only pending passes can be cancelled
    if log_entry.status != 'pending':
        return jsonify({"status": "error", "message": "Only pending passes can be cancelled."}), 400

    # Mark as rejected (or create a new 'cancelled' status if preferred)
    log_entry.status = 'rejected'
    log_entry.decision_time = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"status": "success", "message": "Hall pass request cancelled."})


@api_bp.route('/hall-pass/queue', methods=['GET'])
def get_hall_pass_queue():
    """Get current hall pass queue (approved but not yet checked out) and currently out count
    
    This endpoint supports teacher scoping via query parameter.
    Usage: /api/hall-pass/queue?teacher_id=123
    If no teacher_id is provided and user is logged in as admin, uses session admin_id.
    """
    
    from app.models import Admin
    
    # Determine which teacher's data to show
    teacher_id = request.args.get('teacher_id', type=int)
    
    # If no teacher_id param, try to get from session (if admin is logged in)
    if not teacher_id and session.get('is_admin'):
        teacher_id = session.get('admin_id')
    
    # If still no teacher_id, return error - we need to know which teacher's queue to show
    if not teacher_id:
        return jsonify({
            "status": "error",
            "message": "teacher_id parameter required for queue display"
        }), 400
    
    # Validate teacher exists
    teacher = Admin.query.get(teacher_id)
    if not teacher:
        return jsonify({
            "status": "error",
            "message": "Invalid teacher_id"
        }), 404
    
    # If querying as admin, verify authorization (only their own data unless system admin)
    if session.get('is_admin') and not session.get('is_system_admin'):
        if session.get('admin_id') != teacher_id:
            return jsonify({
                "status": "error",
                "message": "Unauthorized"
            }), 403
    
    # Get hall pass settings for this teacher (or use defaults)
    settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()
    if not settings:
        # Use temporary default settings if none configured for this teacher
        # Note: These are not persisted to the database, just used for this request
        settings = HallPassSettings(teacher_id=teacher_id, queue_enabled=True, queue_limit=10)

    # Get user's timezone from session, default to Pacific Time
    tz_name = session.get('timezone', 'America/Los_Angeles')
    try:
        user_tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        current_app.logger.warning(f"Invalid timezone '{tz_name}' in session, defaulting to Pacific Time.")
        user_tz = pytz.timezone('America/Los_Angeles')

    # Get current time in user's timezone
    now_user_tz = datetime.now(user_tz)

    # Get start of today (midnight) in user's timezone
    today_start_user_tz = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC for database comparison (database stores times in UTC)
    today_start_utc = today_start_user_tz.astimezone(pytz.utc).replace(tzinfo=None)

    # Build subquery for students belonging to this teacher
    # Include both primary ownership (teacher_id) and shared access (student_teachers)
    shared_student_ids = (
        StudentTeacher.query.with_entities(StudentTeacher.student_id)
        .filter(StudentTeacher.admin_id == teacher_id)
        .subquery()
    )
    
    student_ids_subquery = (
        Student.query.with_entities(Student.id)
        .filter(
            or_(
                Student.teacher_id == teacher_id,
                Student.id.in_(shared_student_ids)
            )
        )
        .subquery()
    )

    # Get approved passes from today that haven't been used yet (not left, not returned)
    # SCOPED to this teacher's students
    queue = HallPassLog.query.filter(
        HallPassLog.status == 'approved',
        HallPassLog.decision_time >= today_start_utc,
        HallPassLog.student_id.in_(student_ids_subquery)
    ).order_by(HallPassLog.decision_time.asc()).all()

    # Get count of students currently out from today (status = 'left')
    # SCOPED to this teacher's students
    currently_out_count = HallPassLog.query.filter(
        HallPassLog.status == 'left',
        HallPassLog.left_time >= today_start_utc,
        HallPassLog.student_id.in_(student_ids_subquery)
    ).count()

    # Helper function to ensure times are marked as UTC
    def format_utc_time(dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    queue_data = []
    for log_entry in queue:
        student = log_entry.student
        queue_data.append({
            "student_name": student.full_name,
            "destination": log_entry.reason,
            "pass_number": log_entry.pass_number,
            "approved_time": format_utc_time(log_entry.decision_time),
            "period": log_entry.period
        })

    return jsonify({
        "status": "success",
        "queue": queue_data,
        "currently_out": currently_out_count,
        "total": len(queue_data) + currently_out_count,
        "queue_enabled": settings.queue_enabled,
        "queue_limit": settings.queue_limit
    })


@api_bp.route('/hall-pass/settings', methods=['GET', 'POST'])
@admin_required
def hall_pass_settings():
    """Get or update hall pass settings (admin only)"""
    settings = HallPassSettings.query.first()
    if not settings:
        settings = HallPassSettings(queue_enabled=True, queue_limit=10)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'GET':
        return jsonify({
            "status": "success",
            "settings": {
                "queue_enabled": settings.queue_enabled,
                "queue_limit": settings.queue_limit
            }
        })

    # POST - update settings
    data = request.get_json()

    if 'queue_enabled' in data:
        settings.queue_enabled = bool(data['queue_enabled'])

    if 'queue_limit' in data:
        queue_limit = int(data['queue_limit'])
        if queue_limit < 1 or queue_limit > 50:
            return jsonify({"status": "error", "message": "Queue limit must be between 1 and 50"}), 400
        settings.queue_limit = queue_limit

    settings.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Settings updated successfully",
        "settings": {
            "queue_enabled": settings.queue_enabled,
            "queue_limit": settings.queue_limit
        }
    })


@api_bp.route('/hall-pass/history', methods=['GET'])
@admin_required
def hall_pass_history():
    """Get paginated hall pass history with filters (admin only)"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 25)), 100)  # Max 100 per page

        # Get filter parameters
        period = request.args.get('period', '').strip()
        pass_type = request.args.get('type', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # Import auth helper for tenant scoping
        from app.auth import get_admin_student_query
        
        # Get student IDs that the current admin can access (tenant-scoped)
        # Includes both primary ownership and shared students
        student_ids_subquery = (
            get_admin_student_query(include_unassigned=False)
            .with_entities(Student.id)
            .subquery()
        )

        # Build query with tenant scoping
        query = (
            HallPassLog.query
            .filter(HallPassLog.student_id.in_(student_ids_subquery))
        )

        # Apply filters
        if period:
            query = query.filter(HallPassLog.period == period)

        if pass_type:
            query = query.filter(HallPassLog.reason == pass_type)

        if start_date:
            try:
                # Parse date and treat as UTC midnight (start of day)
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                start_datetime = start_datetime.replace(tzinfo=timezone.utc)
                query = query.filter(HallPassLog.request_time >= start_datetime)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                # Parse date and treat as UTC end of day (23:59:59)
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                query = query.filter(HallPassLog.request_time <= end_datetime)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        # Order by most recent first
        query = query.order_by(HallPassLog.request_time.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        # Helper function to format timestamp as UTC with 'Z' suffix
        def format_timestamp(dt):
            if not dt:
                return None
            # Ensure timestamp is treated as UTC and format properly
            if dt.tzinfo is None:
                # Naive datetime - assume UTC
                return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
            else:
                # Convert to UTC if not already
                return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Format records for response
        records_data = []
        for record in records:
            records_data.append({
                "id": record.id,
                "student_name": record.student.full_name if record.student else "Unknown",
                "period": record.period,
                "reason": record.reason,
                "pass_number": record.pass_number,
                "status": record.status,
                "request_time": format_timestamp(record.request_time),
                "decision_time": format_timestamp(record.decision_time),
                "left_time": format_timestamp(record.left_time),
                "return_time": format_timestamp(record.return_time)
            })

        return jsonify({
            "status": "success",
            "records": records_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching hall pass history: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch history"}), 500


@api_bp.route('/attendance/history', methods=['GET'])
@admin_required
def attendance_history():
    """Get paginated attendance history with filters (admin only)"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 50)), 100)  # Max 100 per page

        # Get filter parameters
        period = request.args.get('period', '').strip()
        block = request.args.get('block', '').strip()
        status = request.args.get('status', '').strip()  # 'active' or 'inactive'
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # Import auth helper for tenant scoping
        from app.auth import get_admin_student_query
        
        # Get student IDs that the current admin can access (tenant-scoped)
        accessible_student_ids_query = get_admin_student_query(include_unassigned=False).with_entities(Student.id)
        
        # Build query scoped to admin's students and exclude deleted records
        query = TapEvent.query.filter(
            TapEvent.student_id.in_(accessible_student_ids_query),
            TapEvent.is_deleted.is_(False)
        )

        # Apply filters
        if period:
            query = query.filter(TapEvent.period == period)

        if status:
            query = query.filter(TapEvent.status == status)

        if start_date:
            try:
                # Parse date and treat as UTC midnight (start of day)
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                start_datetime = start_datetime.replace(tzinfo=timezone.utc)
                query = query.filter(TapEvent.timestamp >= start_datetime)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                # Parse date and treat as UTC end of day (23:59:59)
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                query = query.filter(TapEvent.timestamp <= end_datetime)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        # Filter by block (need to join with Student)
        if block:
            query = query.join(Student, TapEvent.student_id == Student.id)
            # Use LIKE to match comma-separated blocks
            query = query.filter(Student.block.like(f'%{block}%'))

        # Order by most recent first
        query = query.order_by(TapEvent.timestamp.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        # Build student lookup for names and blocks
        student_ids = [r.student_id for r in records]
        students = {s.id: {'name': s.full_name, 'block': s.block} for s in Student.query.filter(Student.id.in_(student_ids)).all()}

        # Get class labels for blocks
        admin_id = session.get("admin_id")
        blocks_in_records = set(students[sid]['block'] for sid in students if students[sid]['block'])
        class_labels = {}
        if blocks_in_records:
            teacher_blocks = TeacherBlock.query.filter(
                TeacherBlock.teacher_id == admin_id,
                TeacherBlock.block.in_(blocks_in_records)
            ).all()
            for teacher_block in teacher_blocks:
                class_labels[teacher_block.block] = teacher_block.get_class_label()

        # Format records for response
        records_data = []
        for record in records:
            student_info = students.get(record.student_id, {'name': 'Unknown', 'block': 'Unknown'})
            student_block = student_info['block']
            student_class_label = class_labels.get(student_block, student_block) if student_block != 'Unknown' else 'Unknown'

            # Format timestamp as UTC with 'Z' suffix
            timestamp_str = None
            if record.timestamp:
                # Ensure timestamp is treated as UTC and format properly
                if record.timestamp.tzinfo is None:
                    # Naive datetime - assume UTC
                    timestamp_str = record.timestamp.replace(tzinfo=timezone.utc).isoformat()
                else:
                    # Convert to UTC if not already
                    timestamp_str = record.timestamp.astimezone(timezone.utc).isoformat()
                # Replace +00:00 with Z for cleaner UTC representation
                timestamp_str = timestamp_str.replace('+00:00', 'Z')

            records_data.append({
                "id": record.id,
                "student_id": record.student_id,
                "student_name": student_info['name'],
                "student_block": student_block,
                "student_class_label": student_class_label,
                "period": record.period,
                "status": record.status,
                "reason": record.reason if record.reason else None,
                "timestamp": timestamp_str
            })

        return jsonify({
            "status": "success",
            "records": records_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching attendance history: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to fetch attendance history"}), 500


# -------------------- ATTENDANCE API --------------------

@api_bp.route('/tap', methods=['POST'])
@limiter.limit("100 per minute")
def handle_tap():
    data = request.get_json()
    safe_data = {k: ('***' if k == 'pin' else v) for k, v in data.items()}
    current_app.logger.info(f"TAP DEBUG: Received data {safe_data}")

    student = get_logged_in_student()

    if not student:
        current_app.logger.warning("TAP ERROR: Unauthenticated tap attempt.")
        return jsonify({"error": "User not logged in or session expired"}), 401

    pin = data.get("pin", "").strip()


    if not check_password_hash(student.pin_hash or '', pin):
        current_app.logger.warning(f"TAP ERROR: Invalid PIN for student {student.id}")
        return jsonify({"error": "Invalid PIN"}), 403


    student_blocks_raw = [b.strip() for b in student.block.split(',') if b.strip()] if student and isinstance(student.block, str) else []
    block_lookup = {b.upper(): b for b in student_blocks_raw}
    valid_periods = list(block_lookup.keys())
    period = data.get("period", "").upper()
    action = data.get("action")

    current_app.logger.info(f"TAP DEBUG: student_id={getattr(student, 'id', None)}, valid_periods={valid_periods}, period={period}, action={action}")

    if period not in valid_periods or action not in ["tap_in", "tap_out"]:
        current_app.logger.warning(f"TAP ERROR: Invalid period or action: period={period}, valid_periods={valid_periods}, action={action}")
        return jsonify({"error": "Invalid period or action"}), 400

    join_code = get_join_code_for_student_period(student.id, period)
    if not join_code:
        current_app.logger.warning(
            f"TAP ERROR: Unable to resolve join_code for student_id={student.id}, period={period}"
        )
        return jsonify({"error": "Unable to resolve class context for this period."}), 400

    now = datetime.now(timezone.utc)

    # --- Check if tap is enabled for this student in this period ---
    from app.models import StudentBlock
    student_block = StudentBlock.query.filter_by(
        student_id=student.id,
        period=period
    ).first()

    # If no StudentBlock record exists, create one with default settings (tap_enabled=True)
    if not student_block:
        try:
            student_block = StudentBlock(
                student_id=student.id,
                period=period,
                tap_enabled=True
            )
            db.session.add(student_block)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=period
            ).first()

    # Check if tap is disabled for this period
    if not student_block.tap_enabled:
        return jsonify({"error": "Tap in/out is currently disabled for this period."}), 403

    # --- Check "done for the day" lock ---
    if action == "tap_in":
        # Use Pacific timezone for "done for the day" check
        pacific = pytz.timezone('America/Los_Angeles')
        now_pacific = now.astimezone(pacific)
        today_pacific = now_pacific.date()

        # Automatically clear "done for the day" lock if it's from a previous day
        if student_block.done_for_day_date is not None and student_block.done_for_day_date < today_pacific:
            student_block.done_for_day_date = None
            db.session.commit()
        if student_block.done_for_day_date == today_pacific:
            return jsonify({"error": "You are done for the day. You cannot tap in again until tomorrow."}), 403


    # --- Hall Pass Logic for Tap Out ---
    if action == 'tap_out':
        reason = data.get("reason")
        if not reason:
            return jsonify({"error": "A reason is required for a hall pass."}), 400

        # Special case for "Done for the day" - this is the old "tap out" behavior
        if reason.lower() in ['done', 'done for the day']:
            # Fall through to the standard TapEvent creation logic below
            pass
        else:
            # All other reasons go through the hall pass approval flow
            # Check hall pass settings and queue limits
            settings = HallPassSettings.query.first()
            if not settings:
                settings = HallPassSettings(queue_enabled=True, queue_limit=10)
                db.session.add(settings)
                db.session.commit()

            # Define restricted pass types (affected by queue system)
            restricted_reasons = ['Restroom', 'Office', 'Locker']
            emergency_reasons = ['Summon', 'Nurse']

            # Check if this is a restricted pass type
            is_restricted = reason in restricted_reasons
            is_emergency = reason in emergency_reasons

            # If queue is disabled, only allow emergency passes
            if not settings.queue_enabled and is_restricted:
                return jsonify({
                    "error": "Queue system is currently disabled. Only Summon and Nurse passes are available."
                }), 403

            # If queue is enabled, check capacity for restricted passes
            if settings.queue_enabled and is_restricted:
                # Get user's timezone from session for today's count
                tz_name = session.get('timezone', 'America/Los_Angeles')
                try:
                    user_tz = pytz.timezone(tz_name)
                except pytz.UnknownTimeZoneError:
                    user_tz = pytz.timezone('America/Los_Angeles')

                now_user_tz = datetime.now(user_tz)
                today_start_user_tz = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)
                today_start_utc = today_start_user_tz.astimezone(pytz.utc).replace(tzinfo=None)

                # Count approved (waiting) passes from today
                queue_count = HallPassLog.query.filter(
                    HallPassLog.status == 'approved',
                    HallPassLog.decision_time >= today_start_utc
                ).count()

                # Count currently out students from today
                out_count = HallPassLog.query.filter(
                    HallPassLog.status == 'left',
                    HallPassLog.left_time >= today_start_utc
                ).count()

                total_occupied = queue_count + out_count

                # Check if queue is at capacity
                if total_occupied >= settings.queue_limit:
                    return jsonify({
                        "error": f"Queue is full ({total_occupied}/{settings.queue_limit}). Please wait for the queue to clear."
                    }), 403

            # Check if hall pass is required (not for Office/Summons/Done for the day)
            should_require_pass = reason.lower() not in ['office', 'summons', 'done for the day']

            if should_require_pass and student.hall_passes <= 0:
                return jsonify({"error": "Insufficient hall passes."}), 400

            # Create a hall pass log entry
            hall_pass_log = HallPassLog(
                student_id=student.id,
                reason=reason,
                period=period,
                join_code=join_code,
                status='pending',
                request_time=now
            )
            db.session.add(hall_pass_log)
            db.session.commit()

            # Since the student is just requesting, they are still 'active'.
            # We need to return the current state to the UI.
            is_active = True
            last_payroll_time = get_last_payroll_time()
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time, join_code=join_code)
            rate_per_second = get_pay_rate_for_block(block_lookup.get(period, period))
            projected_pay = duration * rate_per_second

            return jsonify({
                "status": "ok",
                "message": "Hall pass requested.",
                "active": is_active,
                "duration": duration,
                "projected_pay": projected_pay,
                "hall_pass": {
                    "id": hall_pass_log.id,
                    "status": hall_pass_log.status,
                    "reason": hall_pass_log.reason,
                    "pass_number": hall_pass_log.pass_number
                }
            })

    # --- Standard Tap In/Out Logic ---
    try:
        status = "active" if action == "tap_in" else "inactive"
        reason = data.get("reason") if action == "tap_out" else None

        # Auto-tap-out from other periods when tapping into a new period
        if action == "tap_in":
            # Find all other periods where student is currently active
            for other_period in valid_periods:
                if other_period == period:
                    continue  # Skip the period we're tapping into

                latest_other = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=other_period, is_deleted=False)
                    .filter_by(join_code=join_code)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                if latest_other and latest_other.status == "active":
                    # Auto tap-out from this period
                    auto_tapout = TapEvent(
                        student_id=student.id,
                        period=other_period,
                        status="inactive",
                        timestamp=now,
                        reason="auto_switch",  # Mark as automatic switch
                        join_code=join_code
                    )
                    db.session.add(auto_tapout)
                    current_app.logger.info(f"Auto-tapped out student {student.id} from period {other_period} when tapping into {period}")

        # Prevent duplicate tap-in or tap-out
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=period, is_deleted=False)
            .filter_by(join_code=join_code)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )
        if latest_event and latest_event.status == status:
            current_app.logger.info(f"Duplicate {action} ignored for student {student.id} in period {period}")
            last_payroll_time = get_last_payroll_time()
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time, join_code=join_code)
            return jsonify({
                "status": "ok",
                "active": latest_event.status == "active",
                "duration": duration
            })

        # Check daily limit when tapping IN
        if action == "tap_in":
            from payroll import get_daily_limit_seconds
            from attendance import calculate_period_attendance_utc_range

            daily_limit = get_daily_limit_seconds(period)
            if daily_limit:
                # Use Pacific timezone for daily reset
                pacific = pytz.timezone('America/Los_Angeles')
                now_pacific = now.astimezone(pacific)
                today_pacific = now_pacific.date()

                # Calculate UTC boundaries for today in Pacific timezone
                start_of_day_pacific = pacific.localize(datetime.combine(today_pacific, datetime.min.time()))
                start_of_day_utc = start_of_day_pacific.astimezone(timezone.utc)
                end_of_day_pacific = start_of_day_pacific + timedelta(days=1)
                end_of_day_utc = end_of_day_pacific.astimezone(timezone.utc)

                # Query using proper UTC boundaries
                today_attendance = calculate_period_attendance_utc_range(
                    student.id, period, start_of_day_utc, end_of_day_utc
                )

                if today_attendance >= daily_limit:
                    hours_limit = daily_limit / 3600.0
                    current_app.logger.warning(
                        f"Student {student.id} attempted to tap in for {period} but has reached daily limit of {hours_limit} hours"
                    )
                    return jsonify({
                        "error": f"Daily limit of {hours_limit:.1f} hours reached for this period. Please try again tomorrow."
                    }), 400

        # When tapping in, automatically return any active hall pass
        if action == "tap_in":
            active_hall_pass = HallPassLog.query.filter_by(
                student_id=student.id,
                period=period,
                join_code=join_code,
                status='left'
            ).order_by(HallPassLog.request_time.desc()).first()

            if active_hall_pass:
                active_hall_pass.status = 'returned'
                active_hall_pass.return_time = now
                current_app.logger.info(f"Auto-returned hall pass {active_hall_pass.id} for student {student.id}")

        event = TapEvent(
            student_id=student.id,
            period=period,
            status=status,
            timestamp=now,  # UTC-aware
            reason=reason,
            join_code=join_code
        )
        db.session.add(event)

        # Update "done for the day" status when tapping out with reason "done"
        pacific = pytz.timezone('America/Los_Angeles')
        now_pacific = now.astimezone(pacific)
        today_pacific = now_pacific.date()
        # Clear done_for_day_date if it's a new day
        if student_block.done_for_day_date and student_block.done_for_day_date != today_pacific:
            student_block.done_for_day_date = None
            current_app.logger.info(f"Cleared done_for_day_date for student {student.id} in period {period} (new day)")
        # Set or clear done_for_day_date based on tap out reason
        if action == "tap_out":
            if reason and reason.lower() in ['done', 'done for the day']:
                student_block.done_for_day_date = today_pacific
                current_app.logger.info(f"Student {student.id} marked as done for the day in period {period}")
            else:
                if student_block.done_for_day_date is not None:
                    student_block.done_for_day_date = None
                    current_app.logger.info(f"Cleared done_for_day_date for student {student.id} in period {period} (reason: {reason})")

        db.session.commit()
        current_app.logger.info(f"TAP success - student {student.id} {period} {action}")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"TAP failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500

    # Fetch latest status and unpaid duration for the tapped period
    latest_event = (
        TapEvent.query
        .filter_by(student_id=student.id, period=period, is_deleted=False)
        .filter_by(join_code=join_code)
        .order_by(TapEvent.timestamp.desc())
        .first()
    )
    is_active = latest_event.status == "active" if latest_event else False
    last_payroll_time = get_last_payroll_time()
    duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time, join_code=join_code)

    rate_per_second = get_pay_rate_for_block(block_lookup.get(period, period))
    projected_pay = duration * rate_per_second

    return jsonify({
        "status": "ok",
        "active": is_active,
        "duration": duration,
        "projected_pay": projected_pay
    })


@api_bp.route('/admin/tap-entries/<int:student_id>', methods=['GET'])
def get_tap_entries(student_id):
    """
    Get all tap entries for a student with pairing validation.
    Returns entries grouped by period with pairing status.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    from app.models import Student, TapEvent
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    # Check if admin has access to this student via StudentTeacher association
    # SECURITY: Only use StudentTeacher table, NOT the deprecated teacher_id field
    if student.teachers.filter_by(id=admin.id).count() == 0:
        return jsonify({"error": "Access denied"}), 403

    # Get all tap events for this student
    events = TapEvent.query.filter_by(
        student_id=student_id
    ).order_by(TapEvent.period, TapEvent.timestamp.asc()).all()

    # Group by period and validate pairing
    periods = {}
    for event in events:
        if event.period not in periods:
            periods[event.period] = []
        periods[event.period].append({
            'id': event.id,
            'status': event.status,
            'timestamp': event.timestamp.isoformat() if event.timestamp else None,
            'reason': event.reason,
            'is_deleted': event.is_deleted,
            'deleted_at': event.deleted_at.isoformat() if event.deleted_at else None
        })

    # Validate pairing for each period
    period_data = {}
    for period, events_list in periods.items():
        # Filter out deleted events for pairing validation
        active_events = [e for e in events_list if not e['is_deleted']]

        # Check for unpaired entries
        unpaired = []
        expected_status = 'active'
        for event in active_events:
            if event['status'] == expected_status:
                expected_status = 'inactive' if expected_status == 'active' else 'active'
            else:
                unpaired.append(event['id'])

        # If we end on 'active', the last event is unpaired (student still tapped in)
        if active_events and active_events[-1]['status'] == 'active':
            # This is actually valid (student is currently working), remove from unpaired
            if active_events[-1]['id'] in unpaired:
                unpaired.remove(active_events[-1]['id'])

        period_data[period] = {
            'events': events_list,
            'unpaired_event_ids': unpaired,
            'is_valid': len(unpaired) == 0
        }

    return jsonify({
        'student_id': student_id,
        'student_name': student.full_name,
        'periods': period_data
    })


@api_bp.route('/admin/tap-entries/<int:event_id>', methods=['DELETE'])
def delete_tap_entry(event_id):
    """
    Soft-delete a tap entry by marking it as deleted.
    Only allows deletion of unpaired or invalid entries.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    from app.models import TapEvent, Student
    event = TapEvent.query.get(event_id)
    if not event:
        return jsonify({"error": "Tap entry not found"}), 404

    # Check if admin has access to this student via StudentTeacher association
    # SECURITY: Only use StudentTeacher table, NOT the deprecated teacher_id field
    student = Student.query.get(event.student_id)
    if not student or student.teachers.filter_by(id=admin.id).count() == 0:
        return jsonify({"error": "Access denied"}), 403

    # Mark as deleted
    event.is_deleted = True
    event.deleted_at = datetime.now(timezone.utc)
    event.deleted_by = admin.id

    db.session.commit()

    current_app.logger.info(f"Admin {admin.id} deleted tap entry {event_id} for student {event.student_id}")

    return jsonify({
        "status": "ok",
        "message": "Tap entry deleted successfully"
    })


@api_bp.route('/admin/student-block-settings', methods=['POST'])
def update_student_block_settings():
    """
    Update StudentBlock settings (tap_enabled toggle) for a student-period combination.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    student_id = data.get('student_id')
    period = data.get('period', '').upper()
    tap_enabled = data.get('tap_enabled')

    if not student_id or not period or tap_enabled is None:
        return jsonify({"error": "Missing required fields"}), 400

    from app.models import Student, StudentBlock
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    # Check if admin has access to this student (many-to-many or legacy teacher_id)
    if not (student.teachers.filter_by(id=admin.id).first() or student.teacher_id == admin.id):
        return jsonify({"error": "Access denied"}), 403

    # Get or create StudentBlock record
    student_block = StudentBlock.query.filter_by(
        student_id=student_id,
        period=period
    ).first()

    if not student_block:
        student_block = StudentBlock(
            student_id=student_id,
            period=period,
            tap_enabled=tap_enabled
        )
        db.session.add(student_block)
    else:
        student_block.tap_enabled = tap_enabled

    db.session.commit()

    current_app.logger.info(f"Admin {admin.id} set tap_enabled={tap_enabled} for student {student_id} period {period}")

    return jsonify({
        "status": "ok",
        "tap_enabled": tap_enabled
    })


def check_and_auto_tapout_if_limit_reached(student):
    """
    Checks if an active student has reached their daily limit and auto-taps them out.
    This function should be called periodically (e.g., during status checks).
    Daily limits reset at midnight Pacific time.
    """
    import pytz
    from payroll import get_daily_limit_seconds
    from attendance import calculate_period_attendance_utc_range

    # Helper function to ensure UTC timezone-aware datetime
    def _as_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # Helper function to ensure UTC timezone-aware datetime
    def _as_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # Keep original case for settings lookup, but uppercase for TapEvent queries
    student_blocks = [b.strip() for b in student.block.split(',') if b.strip()]
    now_utc = datetime.now(timezone.utc)

    # Use Pacific timezone for daily reset
    pacific = pytz.timezone('America/Los_Angeles')
    now_pacific = now_utc.astimezone(pacific)
    today_pacific = now_pacific.date()

    # Calculate UTC boundaries for today in Pacific timezone
    # Start: midnight Pacific today -> UTC
    start_of_day_pacific = pacific.localize(datetime.combine(today_pacific, datetime.min.time()))
    start_of_day_utc = start_of_day_pacific.astimezone(timezone.utc)

    # End: midnight Pacific tomorrow -> UTC
    end_of_day_pacific = start_of_day_pacific + timedelta(days=1)
    end_of_day_utc = end_of_day_pacific.astimezone(timezone.utc)

    for block_original in student_blocks:
        period_upper = block_original.upper()

        # Check if student is currently active in this period (TapEvent uses uppercase)
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=period_upper)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )

        if latest_event and latest_event.status == "active":
            # Get daily limit for this period (use original case for settings lookup)
            daily_limit = get_daily_limit_seconds(block_original)

            if daily_limit:
                # Calculate today's completed attendance using proper Pacific day boundaries
                today_attendance = calculate_period_attendance_utc_range(
                    student.id, period_upper, start_of_day_utc, end_of_day_utc
                )

                # Add current active session time
                # Convert to UTC-aware datetime to prevent TypeError
                last_tap_in_utc = _as_utc(latest_event.timestamp)

                # Only add active session time if tapped in today (within Pacific day boundaries)
                if start_of_day_utc <= last_tap_in_utc < end_of_day_utc:
                    current_session_seconds = (now_utc - last_tap_in_utc).total_seconds()
                    today_attendance += current_session_seconds

                # If limit reached or exceeded, auto-tap-out
                if today_attendance >= daily_limit:
                    hours_limit = daily_limit / 3600.0
                    current_app.logger.info(
                        f"Auto-tapping out student {student.id} from {period_upper} - daily limit of {hours_limit} hours reached (total: {today_attendance/3600:.2f}h)"
                    )

                    # Get join_code for this student-period combination
                    join_code = get_join_code_for_student_period(student.id, period_upper)
                    if not join_code:
                        current_app.logger.warning(
                            f"Unable to resolve join_code for student {student.id} in period {period_upper} - skipping auto-tap-out"
                        )
                        continue

                    # Calculate when they SHOULD have been tapped out (at exactly the limit)
                    # If they've been active for 90 minutes and limit is 75, tap them out 15 minutes ago
                    overage_seconds = today_attendance - daily_limit
                    tapout_timestamp = now_utc - timedelta(seconds=overage_seconds)

                    # Create tap-out event backdated to when they hit the limit
                    tap_out_event = TapEvent(
                        student_id=student.id,
                        period=period_upper,
                        status="inactive",
                        timestamp=tapout_timestamp,
                        reason=f"Daily limit ({hours_limit:.1f}h) reached",
                        join_code=join_code
                    )
                    db.session.add(tap_out_event)

    # Commit all auto-tap-outs at once
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to auto-tap-out student {student.id}: {e}")


@api_bp.route('/student-status', methods=['GET'])
@login_required
def student_status():
    from app.routes.student import get_current_class_context

    student = get_logged_in_student()

    context = get_current_class_context()
    if not context:
        return jsonify({"status": "error", "message": "No class selected."}), 400

    # Check and auto-tap-out if daily limit reached
    check_and_auto_tapout_if_limit_reached(student)

    period_states = get_all_block_statuses(student, join_code=context['join_code'])

    return jsonify({
        "status": "ok",
        "periods": period_states
    })


# -------------------- UTILITY API --------------------

@api_bp.route('/set-timezone', methods=['POST'])
def set_timezone():
    """Store user's timezone in session for datetime formatting"""
    # Allow access if user is logged in as student OR admin
    is_authenticated = False
    now = datetime.now(timezone.utc)

    # Check Admin Session
    if session.get('is_admin'):
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity)
                if (now - last_activity_dt) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass # Invalid date format, treat as unauthenticated
        else:
             # If no last_activity but is_admin is set, treat as active for now
             # (matches admin_required logic which would set it if missing)
             is_authenticated = True
             session['last_activity'] = now.isoformat()

    # Check Student Session (if not already authenticated as admin)
    if not is_authenticated and 'student_id' in session:
        login_time_str = session.get('login_time')
        if login_time_str:
            try:
                login_time = datetime.fromisoformat(login_time_str)
                if (now - login_time) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass

    if not is_authenticated:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json()
    timezone_name = data.get('timezone')

    if not timezone_name:
        return jsonify({"status": "error", "message": "Timezone is required."}), 400

    # Validate Timezone
    if timezone_name not in pytz.all_timezones:
         return jsonify({"status": "error", "message": "Invalid timezone."}), 400

    # Store in session
    session['timezone'] = timezone_name
    current_app.logger.info(f"Timezone set to {timezone_name} for session")

    return jsonify({"status": "success", "message": f"Timezone set to {timezone_name}."})


# -------------------- VIEW AS STUDENT API --------------------

@api_bp.route('/admin/create-demo-student', methods=['POST'])
@admin_required
def create_demo_student():
    """Create a demo student session with custom configuration"""
    from app.models import DemoStudent
    from werkzeug.security import generate_password_hash
    import secrets

    try:
        admin_id = session.get('admin_id')
        data = request.get_json()

        # Extract configuration
        checking_balance = float(data.get('checking_balance', 0))
        savings_balance = float(data.get('savings_balance', 0))
        hall_passes = int(data.get('hall_passes', 3))
        insurance_plan = data.get('insurance_plan', 'none')
        period = data.get('period', 'A')
        rent_enabled = bool(data.get('rent_enabled', True))

        # Generate a unique session ID for this demo
        demo_session_id = secrets.token_urlsafe(32)

        # Create a temporary demo student record
        # Use encrypted first name for demo student
        demo_student = Student(
            first_name='Demo',
            last_initial='S',
            block=period,
            salt=secrets.token_bytes(16),
            pin_hash=generate_password_hash('1234'),  # Default PIN for demo
            passphrase_hash=generate_password_hash('demo'),  # Default passphrase for demo
            hall_passes=hall_passes,
            is_rent_enabled=rent_enabled,
            insurance_plan=insurance_plan,
            has_completed_setup=True,
            teacher_id=admin_id
        )
        demo_student.first_half_hash = secrets.token_hex(32)
        demo_student.second_half_hash = secrets.token_hex(32)

        db.session.add(demo_student)
        db.session.flush()  # Get the student ID

        # Create initial balance transactions
        if checking_balance > 0:
            checking_tx = Transaction(
                student_id=demo_student.id,
                teacher_id=admin_id,
                amount=checking_balance,
                account_type='checking',
                type='admin_adjustment',
                description='Demo student initial balance'
            )
            db.session.add(checking_tx)

        if savings_balance > 0:
            savings_tx = Transaction(
                student_id=demo_student.id,
                teacher_id=admin_id,
                amount=savings_balance,
                account_type='savings',
                type='admin_adjustment',
                description='Demo student initial balance'
            )
            db.session.add(savings_tx)

        # Create demo session record
        demo_session = DemoStudent(
            admin_id=admin_id,
            student_id=demo_student.id,
            session_id=demo_session_id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            config_checking_balance=checking_balance,
            config_savings_balance=savings_balance,
            config_hall_passes=hall_passes,
            config_insurance_plan=insurance_plan,
            config_is_rent_enabled=rent_enabled,
            config_period=period
        )
        db.session.add(demo_session)
        db.session.commit()

        current_app.logger.info(f"Admin {admin_id} created demo student session {demo_session_id} with student_id={demo_student.id}")

        # Return success with the session ID
        return jsonify({
            "status": "success",
            "message": "Demo student session created successfully",
            "session_id": demo_session_id,
            "redirect_url": f"/student/demo-login/{demo_session_id}"
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create demo student: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Failed to create demo student session. Please try again."
        }), 500


@api_bp.route('/admin/block-tap-settings', methods=['GET'])
@admin_required
def get_block_tap_settings():
    """
    Get tap_enabled settings for all students in a specific block.
    Returns true if any student has tap enabled, false if all are disabled.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401
    
    block = request.args.get('block', '').strip().upper()
    if not block:
        return jsonify({"error": "Block parameter is required"}), 400
    
    from app.models import Student, StudentBlock
    from app.auth import get_admin_student_query
    
    # Get all students for this admin in this block
    students = get_admin_student_query().all()
    students_in_block = [
        s for s in students
        if s.block and block.upper() in [b.strip().upper() for b in s.block.split(',')]
    ]
    
    if not students_in_block:
        # No students in this block, default to enabled
        return jsonify({"tap_enabled": True})
    
    # Check if tap is enabled for any student in this block
    # Returns the overall block state: true if at least one student has tap enabled,
    # false if all students have it disabled
    any_enabled = False
    for student in students_in_block:
        student_block = StudentBlock.query.filter_by(
            student_id=student.id,
            period=block
        ).first()
        
        if student_block:
            if student_block.tap_enabled:
                any_enabled = True
                break
        else:
            # No StudentBlock record means tap is enabled by default
            any_enabled = True
            break
    
    return jsonify({"tap_enabled": any_enabled})


@api_bp.route('/admin/block-tap-settings', methods=['POST'])
@admin_required
def update_block_tap_settings():
    """
    Update tap_enabled settings for all students in a specific block/period.
    This sets the tap_enabled flag for all students in the specified block.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    block = data.get('block', '').strip().upper()
    tap_enabled = data.get('tap_enabled')
    
    if not block or tap_enabled is None:
        return jsonify({"error": "Missing required fields"}), 400
    
    from app.models import Student, StudentBlock
    from app.auth import get_admin_student_query
    
    try:
        # Get all students for this admin in this block
        students = get_admin_student_query().all()
        students_in_block = [
            s for s in students
            if s.block and block.upper() in [b.strip().upper() for b in s.block.split(',')]
        ]
        
        updated_count = 0
        for student in students_in_block:
            # Get or create StudentBlock record
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=block
            ).first()
            
            if not student_block:
                student_block = StudentBlock(
                    student_id=student.id,
                    period=block,
                    tap_enabled=tap_enabled
                )
                db.session.add(student_block)
            else:
                student_block.tap_enabled = tap_enabled
            
            updated_count += 1
        
        db.session.commit()
        
        current_app.logger.info(
            f"Admin {admin.id} set tap_enabled={tap_enabled} for {updated_count} students in block {block}"
        )
        
        return jsonify({
            "status": "ok",
            "tap_enabled": tap_enabled,
            "updated_count": updated_count
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating block tap settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to update tap settings"}), 500


@api_bp.route('/admin/view-as-student-status', methods=['GET'])
@admin_required
def view_as_student_status():
    """Get the current view-as-student mode status"""
    return jsonify({
        "status": "success",
        "view_as_student": session.get('view_as_student', False)
    })
