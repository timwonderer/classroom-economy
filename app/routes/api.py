"""
API routes for Classroom Token Hub.

RESTful JSON API endpoints for student transactions, hall passes, attendance,
and other interactive features. Most routes require authentication.
"""

import random
import string
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import (
    Student, StoreItem, StudentItem, Transaction, TapEvent,
    HallPassLog, InsuranceClaim
)
from app.auth import login_required, admin_required, get_logged_in_student

# Import external modules
from attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    get_all_block_statuses
)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


# -------------------- STORE API --------------------

@api_bp.route('/purchase-item', methods=['POST'])
@login_required
def purchase_item():
    student = get_logged_in_student()
    data = request.get_json()
    item_id = data.get('item_id')
    passphrase = data.get('passphrase')

    if not all([item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    item = StoreItem.query.get(item_id)

    # 2. Validate item and purchase conditions
    if not item or not item.is_active:
        return jsonify({"status": "error", "message": "This item is not available."}), 404

    if student.checking_balance < item.price:
        return jsonify({"status": "error", "message": "Insufficient funds."}), 400

    if item.inventory is not None and item.inventory <= 0:
        return jsonify({"status": "error", "message": "This item is out of stock."}), 400

    if item.limit_per_student is not None:
        if item.item_type == 'hall_pass':
            # For hall passes, check transaction history since no StudentItem is created
            purchase_count = Transaction.query.filter_by(
                student_id=student.id,
                type='purchase',
                description=f"Purchase: {item.name}"
            ).count()
        else:
            purchase_count = StudentItem.query.filter_by(student_id=student.id, store_item_id=item.id).count()
        if purchase_count >= item.limit_per_student:
            return jsonify({"status": "error", "message": "You have reached the purchase limit for this item."}), 400

    # 3. Process the transaction
    try:
        # Deduct from checking account
        purchase_tx = Transaction(
            student_id=student.id,
            amount=-item.price,
            account_type='checking',
            type='purchase',
            description=f"Purchase: {item.name}"
        )
        db.session.add(purchase_tx)

        # Handle inventory
        if item.inventory is not None:
            item.inventory -= 1

        # --- Handle special item type: Hall Pass ---
        if item.item_type == 'hall_pass':
            student.hall_passes += 1
            db.session.commit()
            return jsonify({"status": "success", "message": f"You purchased a Hall Pass! Your new balance is {student.hall_passes}."})

        # --- Standard Item Logic ---
        # Create the student's item
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

        new_student_item = StudentItem(
            student_id=student.id,
            store_item_id=item.id,
            purchase_date=datetime.now(timezone.utc),
            expiry_date=expiry_date,
            status=student_item_status
        )
        db.session.add(new_student_item)
        db.session.commit()

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
                db.session.commit()
                # This flash won't be seen by the user due to the JSON response,
                # but it's good for logging/debugging. A more robust solution might use websockets.
                current_app.logger.info(f"Collective goal '{item.name}' for block {student.block} has been met!")

        return jsonify({"status": "success", "message": f"You purchased {item.name}!"})

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
    details = data.get('details', '')  # optional notes from student

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
    if student_item.status not in ['purchased', 'pending']:
        return jsonify({"status": "error", "message": "This item has already been used or is not available."}), 400

    # Check expiry
    if student_item.expiry_date and datetime.now(timezone.utc) > student_item.expiry_date:
        student_item.status = 'expired'
        db.session.commit()
        return jsonify({"status": "error", "message": "This item has expired."}), 400

    # 3. Mark as processing and create redemption transaction
    try:
        student_item.status = 'processing'
        student_item.redemption_date = datetime.now(timezone.utc)
        student_item.redemption_details = details

        # Create a redemption transaction (deduct the value from savings or checking)
        # This is a $0 transaction to log the redemption event
        redemption_tx = Transaction(
            student_id=student.id,
            amount=0.0,
            account_type='checking',
            type='redemption',
            description=f"Used: {student_item.store_item.name}"
        )
        db.session.add(redemption_tx)
        db.session.commit()

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
            period="HALLPASS", # Use a special period for hall pass events
            status='inactive',
            timestamp=now,
            reason=log_entry.reason
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
            period="HALLPASS",
            status='active',
            timestamp=now,
            reason="Return from hall pass"
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
        period="HALLPASS",
        status='inactive',
        timestamp=now,
        reason=log_entry.reason
    )
    db.session.add(tap_out_event)

    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"{log_entry.student.full_name} has left for {log_entry.reason}.",
            "student_name": log_entry.student.full_name
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
        period="HALLPASS",
        status='active',
        timestamp=now,
        reason="Returned from hall pass"
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


# -------------------- ATTENDANCE API --------------------

@api_bp.route('/tap', methods=['POST'])
def handle_tap():
    print("🛠️ TAP ROUTE HIT")
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


    valid_periods = [b.strip().upper() for b in student.block.split(',') if b.strip()] if student and isinstance(student.block, str) else []
    period = data.get("period", "").upper()
    action = data.get("action")

    current_app.logger.info(f"TAP DEBUG: student_id={getattr(student, 'id', None)}, valid_periods={valid_periods}, period={period}, action={action}")

    if period not in valid_periods or action not in ["tap_in", "tap_out"]:
        current_app.logger.warning(f"TAP ERROR: Invalid period or action: period={period}, valid_periods={valid_periods}, action={action}")
        return jsonify({"error": "Invalid period or action"}), 400

    now = datetime.now(timezone.utc)


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
            # Check if hall pass is required (not for Office/Summons/Done for the day)
            should_require_pass = reason.lower() not in ['office', 'summons', 'done for the day']

            if should_require_pass and student.hall_passes <= 0:
                return jsonify({"error": "Insufficient hall passes."}), 400

            # Create a hall pass log entry
            hall_pass_log = HallPassLog(
                student_id=student.id,
                reason=reason,
                period=period,
                status='pending',
                request_time=now
            )
            db.session.add(hall_pass_log)
            db.session.commit()

            # Since the student is just requesting, they are still 'active'.
            # We need to return the current state to the UI.
            is_active = True
            last_payroll_time = get_last_payroll_time()
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time)
            RATE_PER_SECOND = 0.25 / 60
            projected_pay = duration * RATE_PER_SECOND

            return jsonify({
                "status": "ok",
                "message": "Hall pass requested.",
                "active": is_active,
                "duration": duration,
                "projected_pay": projected_pay
            })

    # --- Standard Tap In/Out Logic ---
    try:
        status = "active" if action == "tap_in" else "inactive"
        reason = data.get("reason") if action == "tap_out" else None

        # Prevent duplicate tap-in or tap-out
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=period)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )
        if latest_event and latest_event.status == status:
            current_app.logger.info(f"Duplicate {action} ignored for student {student.id} in period {period}")
            last_payroll_time = get_last_payroll_time()
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time)
            return jsonify({
                "status": "ok",
                "active": latest_event.status == "active",
                "duration": duration
            })

        # Check daily limit when tapping IN
        if action == "tap_in":
            import pytz
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
            reason=reason
        )
        db.session.add(event)
        db.session.commit()
        current_app.logger.info(f"TAP success - student {student.id} {period} {action}")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"TAP failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500

    # Fetch latest status and unpaid duration for the tapped period
    latest_event = (
        TapEvent.query
        .filter_by(student_id=student.id, period=period)
        .order_by(TapEvent.timestamp.desc())
        .first()
    )
    is_active = latest_event.status == "active" if latest_event else False
    last_payroll_time = get_last_payroll_time()
    duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time)

    RATE_PER_SECOND = 0.25 / 60
    projected_pay = duration * RATE_PER_SECOND

    return jsonify({
        "status": "ok",
        "active": is_active,
        "duration": duration,
        "projected_pay": projected_pay
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

    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
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

    for period in student_blocks:
        # Check if student is currently active in this period
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=period)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )

        if latest_event and latest_event.status == "active":
            # Get daily limit for this period
            daily_limit = get_daily_limit_seconds(period)

            if daily_limit:
                # Calculate today's completed attendance using proper Pacific day boundaries
                today_attendance = calculate_period_attendance_utc_range(
                    student.id, period, start_of_day_utc, end_of_day_utc
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
                        f"Auto-tapping out student {student.id} from {period} - daily limit of {hours_limit} hours reached (total: {today_attendance/3600:.2f}h)"
                    )

                    # Create tap-out event
                    tap_out_event = TapEvent(
                        student_id=student.id,
                        period=period,
                        status="inactive",
                        timestamp=now_utc,
                        reason=f"Daily limit ({hours_limit:.1f}h) reached"
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
    student = get_logged_in_student()

    # Check and auto-tap-out if daily limit reached
    check_and_auto_tapout_if_limit_reached(student)

    period_states = get_all_block_statuses(student)

    return jsonify({
        "status": "ok",
        "periods": period_states
    })


# -------------------- UTILITY API --------------------

@api_bp.route('/set-timezone', methods=['POST'])
@login_required
def set_timezone():
    """Store user's timezone in session for datetime formatting"""
    data = request.get_json()
    timezone_name = data.get('timezone')

    if not timezone_name:
        return jsonify({"status": "error", "message": "Timezone is required."}), 400

    # Store in session
    session['timezone'] = timezone_name
    current_app.logger.info(f"Timezone set to {timezone_name} for session")

    return jsonify({"status": "success", "message": f"Timezone set to {timezone_name}."})
