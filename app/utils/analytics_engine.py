from __future__ import annotations

"""
Analytics Engine for Classroom Economy

Implements analytics computation per docs/technical-reference/analytics-specification.md.

Core Principles:
- All monetary metrics are CWI-relative (not absolute)
- Trends matter more than totals
- System health focus, not student ranking
- No leaderboards or comparative student ranking
- Metrics precomputed and cached by time window
- 5-second readability target for system health metrics

Per spec section 4.2:
- Must be trend-based
- Must include directionality (improving/worsening)
- Must never default to blaming students
"""

from datetime import datetime, timezone
from app.utils.canonical_temporal_resolver import utc_now
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from types import SimpleNamespace
from sqlalchemy import true
import sqlalchemy as sa

from app.extensions import db
from app.models import (
    Transaction, AttendanceSession, PayrollSettings,
    RentSettings, ClassEconomy,
    Seat, IdentityProfile
)
from app.utils.economy_balance import EconomyBalanceChecker
from app.utils.economy_policy import (
    get_active_policy_mode_for_class,
    get_analytics_policy,
    get_policy_profile,
)
from app.utils.join_code import get_display_join_code
from app.feats.base import requires_feat_context
import logging


@dataclass
class SystemHealthMetrics:
    """System health metrics (always visible per spec section 4.1)"""
    participation_rate: float  # % of students who were active
    money_velocity: float  # Transactions per student per day
    cwi_deviation_within_20pct: float  # % of students within ±20% of expected CWI
    budget_survival_pass_rate: float  # % of students passing budget survival test
    cwi_value: float  # Current CWI for context
    total_students: int
    active_students: int


@dataclass
class TrendMetrics:
    """Drift & anomaly metrics (trend-based per spec section 4.2)"""
    balance_trend: str  # 'increasing', 'stable', 'decreasing'
    velocity_trend: str  # 'increasing', 'stable', 'decreasing'
    participation_trend: str  # 'increasing', 'stable', 'decreasing'


@dataclass
class AnalyticsWindowView:
    window_type: str
    window_start: datetime
    window_end: datetime
    participation_rate: float
    money_velocity: float
    cwi_deviation_within_20pct: float
    budget_survival_pass_rate: float
    cwi_value: float
    avg_student_balance: float
    balance_trend: str
    velocity_trend: str
    participation_trend: str
    total_students: int
    active_students: int
    total_transactions: int
    computed_at: datetime
    is_complete: bool


class AnalyticsEngine:
    """
    Core analytics computation engine.
    
    Implements observability model per spec section 2:
    - Surface signals, not raw data
    - Highlight anomalies, not totals
    - Favor trends over snapshots
    - Bias toward actionable interpretation
    """
    
    def __init__(self, class_id: str):
        """
        Initialize analytics engine for a specific class economy.

        Args:
            class_id: The canonical class identifier (UUID).
        """
        class_row = db.session.get(ClassEconomy, class_id)
        if not class_row:
            raise ValueError(f"Invalid class lookup: class_id={class_id}")

        self.class_id = class_row.class_id
        self.teacher_id = class_row.teacher_user_id
        self.user_id = class_row.teacher_user_id
        self.join_code = get_display_join_code(class_row.class_id)
        self.policy_mode = get_active_policy_mode_for_class(self.class_id)
        self.policy_profile = get_policy_profile(self.policy_mode)
        self.analytics_policy = get_analytics_policy(self.policy_mode)
        self.economy_checker = EconomyBalanceChecker(
            self.teacher_id,
            policy_mode=self.policy_mode,
            class_id=self.class_id,
        )


    def _get_enrolled_students(self) -> List[Seat]:
        """Get all student seats enrolled in this class period via canonical class membership."""
        if not self.class_id:
            return []
        return (
            Seat.query
            .filter(
                Seat.class_id == self.class_id,
                Seat.role == 'student',
                Seat.claimed_at.isnot(None),
            )
            .all()
        )

    def _get_seat_id_by_student(self, student_ids: List[int]) -> Dict[int, int]:
        if not self.class_id or not student_ids:
            return {}
        rows = (
            Seat.query.with_entities(Seat.id, Seat.user_id)
            .filter(
                Seat.class_id == self.class_id,
                Seat.user_id.in_(student_ids),
            )
            .all()
        )
        return {student_id: seat_id for seat_id, student_id in rows if student_id and seat_id}
    
    def _get_cwi(self) -> float:
        """Calculate current CWI for this class."""
        if not self.class_id:
            return 0.0

        payroll_settings = (
            PayrollSettings.query.filter(
                PayrollSettings.class_id == self.class_id,
            )
            .order_by(sa.desc(PayrollSettings.block.isnot(None)))
            .first()
        )
        
        if not payroll_settings:
            return 0.0
        
        cwi_calc = self.economy_checker.calculate_cwi(payroll_settings)
        if cwi_calc is None:
            return 0.0
        return cwi_calc.cwi
    
    def calculate_participation_rate(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> Tuple[float, int, int]:
        """
        Calculate participation rate for time window.
        
        Returns:
            Tuple of (participation_rate, active_students, total_students)
        """
        students = self._get_enrolled_students()
        total_students = len(students)
        if total_students == 0:
            return 0.0, 0, 0
        
        # Count students with any activity (transactions or attendance)
        enrolled_seat_ids = {seat.id for seat in students}
        active_seat_ids = set()
        
        # Check for transactions in window (distinct seat IDs)
        transaction_seat_rows = (
            Transaction.query.with_entities(Transaction.seat_id)
            .filter(
                Transaction.class_id == self.class_id,
                Transaction.timestamp >= window_start,
                Transaction.timestamp < window_end,
                Transaction.seat_id.isnot(None)
            )
            .distinct()
            .all()
        )
        for (seat_id,) in transaction_seat_rows:
            if seat_id in enrolled_seat_ids:
                active_seat_ids.add(seat_id)
        
        att_seat_rows = (
            AttendanceSession.query.with_entities(AttendanceSession.target_seat_id)
            .filter(
                AttendanceSession.class_id == self.class_id,
                AttendanceSession.timestamp >= window_start,
                AttendanceSession.timestamp < window_end,
            )
            .distinct()
            .all()
        )
        for (seat_id,) in att_seat_rows:
            if seat_id in enrolled_seat_ids:
                active_seat_ids.add(seat_id)
        
        active_students = len(active_seat_ids)
        participation_rate = (active_students / total_students) * 100
        
        return participation_rate, active_students, total_students
    
    def calculate_money_velocity(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> float:
        """
        Calculate money velocity: transactions per student per day.
        
        This measures how actively money is moving through the economy.
        Per spec, this is a system health metric.
        """
        students = self._get_enrolled_students()
        total_students = len(students)
        
        if total_students == 0:
            return 0.0
        
        # Calculate days in window (allow fractional days for sub-day windows)
        duration_seconds = (window_end - window_start).total_seconds()
        if duration_seconds <= 0:
            return 0.0
        days = duration_seconds / 86400.0
        transaction_count = Transaction.query.filter(
            Transaction.class_id == self.class_id,
            Transaction.timestamp >= window_start,
            Transaction.timestamp < window_end,
            ~Transaction.is_void
        ).count()
        
        # Transactions per student per day
        velocity = transaction_count / (total_students * days)
        
        return round(velocity, 2)
    
    def calculate_cwi_deviation_distribution(
        self,
        window_start: datetime,
        window_end: datetime,
        cwi: float
    ) -> float:
        """
        Calculate % of students within CWI deviation bands.
        
        Per spec section 3.2 and 4.1:
        - All monetary analytics must be CWI-relative
        - Report % of students within defined CWI bands (±20%)
        
        Returns:
            Percentage of students within ±20% of expected CWI trajectory
        """
        students = self._get_enrolled_students()
        total_students = len(students)

        if total_students == 0 or cwi == 0:
            return 0.0
        
        # Calculate expected balance based on window duration
        # Assuming perfect attendance, expected balance = CWI * weeks
        days = (window_end - window_start).days
        weeks = days / 7.0
        expected_balance = cwi * weeks
        
        # Count students within ±20% of expected
        from app.services.ledger_service import get_available_balance

        within_band = 0
        
        for student in students:
            current_balance = get_available_balance(student.id, self.class_id, 'checking')

            # Convert Decimal to float for arithmetic operations
            current_balance = float(current_balance) if current_balance is not None else 0.0

            # Calculate deviation
            if expected_balance > 0:
                deviation = abs(current_balance - expected_balance) / expected_balance
                if deviation <= self.analytics_policy["cwi_deviation_band"]:
                    within_band += 1
            elif current_balance == 0:
                # If expected is 0 and actual is 0, that's within band
                within_band += 1
        
        percentage = (within_band / total_students) * 100
        return round(percentage, 1)
    
    def calculate_budget_survival_pass_rate(self, cwi: float) -> float:
        """
        Calculate % of students passing budget survival test.
        
        Per DOM-CLASS-002 and economy policy modes:
        - Students with perfect attendance must meet policy-mode minimum savings ratio of CWI
        - This tests if economy is balanced
        """

        students = self._get_enrolled_students()
        total_students = len(students)
        if total_students == 0:
            return 0.0
        
        if cwi <= 0:
            logging.warning(
                "Invalid CWI (%s) for user_id=%s, class_id=%s. "
                "Check PayrollSettings configuration.",
                cwi,
                self.user_id,
                self.class_id,
            )
            return 0.0

        savings_ratio = float(
            self.policy_profile.get("ratios", {}).get("savings_weekly", {}).get("min", 0.10)
        )
        passing_students = 0
        from app.services.ledger_service import get_available_balance
        
        for student in students:
            balance = get_available_balance(student.id, self.class_id, 'checking')

            # Convert Decimal to float for arithmetic comparison
            balance = float(balance) if balance is not None else 0.0

            # Check if the student can save at least the policy-governed CWI minimum.
            if balance >= savings_ratio * cwi:
                passing_students += 1
        
        percentage = (passing_students / total_students) * 100
        return round(percentage, 1)
    
    def calculate_trend(
        self,
        current_value: float,
        previous_value: Optional[float],
        threshold: float = 0.10
    ) -> str:
        """
        Determine trend direction based on change.
        
        Args:
            current_value: Current metric value
            previous_value: Previous period value (None if no history)
            threshold: Minimum percent change to consider significant (default 10%)

        Returns:
            'increasing', 'stable', or 'decreasing'.
        
        Notes:
            Per spec sections 4.1 and 4.2, these are class-level, auto-updating,
            readable within 5 seconds, and trend-based with clear directionality.
        """
        if previous_value is None or previous_value == 0:
            return 'stable'
        
        change = (current_value - previous_value) / previous_value
        
        if abs(change) < threshold:
            return 'stable'
        elif change > 0:
            return 'increasing'  # Changed from 'improving' to 'increasing'
        else:
            return 'decreasing'  # Changed from 'worsening' to 'decreasing'
    
    def compute_system_health(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> SystemHealthMetrics:
        """
        Compute all system health metrics for a time window.
        
        Per spec section 4.1:
        - Aggregated at class level
        - Auto-updating
        - Readable in under 5 seconds
        """
        cwi = self._get_cwi()
        
        participation_rate, active_students, total_students = self.calculate_participation_rate(
            window_start, window_end
        )
        
        money_velocity = self.calculate_money_velocity(window_start, window_end)
        
        cwi_deviation_pct = self.calculate_cwi_deviation_distribution(
            window_start, window_end, cwi
        )
        
        budget_survival_rate = self.calculate_budget_survival_pass_rate(cwi)
        
        return SystemHealthMetrics(
            participation_rate=participation_rate,
            money_velocity=money_velocity,
            cwi_deviation_within_20pct=cwi_deviation_pct,
            budget_survival_pass_rate=budget_survival_rate,
            cwi_value=cwi,
            total_students=total_students,
            active_students=active_students
        )
    
    def compute_trends(
        self,
        current_snapshot: SystemHealthMetrics,
        previous_snapshot: Optional[AnalyticsWindowView]
    ) -> TrendMetrics:
        """
        Compute trend indicators by comparing to previous period.
        
        Per spec section 4.2:
        - Must be trend-based
        - Must include directionality (improving/worsening)
        - Must never default to blaming students
        """
        if previous_snapshot is None:
            # No history, all stable
            return TrendMetrics(
                balance_trend='stable',
                velocity_trend='stable',
                participation_trend='stable'
            )
        
        # Calculate trends (higher is better for all these metrics)
        velocity_trend = self.calculate_trend(
            current_snapshot.money_velocity,
            previous_snapshot.money_velocity
        )
        
        participation_trend = self.calculate_trend(
            current_snapshot.participation_rate,
            previous_snapshot.participation_rate
        )
        
        balance_trend = self.calculate_trend(
            current_snapshot.cwi_deviation_within_20pct,
            previous_snapshot.cwi_deviation_within_20pct
        )
        
        return TrendMetrics(
            balance_trend=balance_trend,
            velocity_trend=velocity_trend,
            participation_trend=participation_trend
        )
    
    def generate_alerts(
        self,
        metrics: SystemHealthMetrics,
        trends: TrendMetrics
    ) -> List[Dict]:
        """
        Generate alerts based on metrics and thresholds.
        
        Per spec section 6:
        - Visual alerts only (not notifications)
        - Explain what changed, why it matters, suggest interventions
        - Never shame students, prescribe discipline, or trigger penalties
        """
        alerts = []
        
        # Alert: Low participation
        if metrics.participation_rate < (self.analytics_policy["participation_warning_threshold"] * 100):
            alerts.append({
                'alert_key': 'participation_low',
                'severity': 'warning',
                'what_changed': f'Participation rate is {metrics.participation_rate:.1f}%',
                'why_it_matters': 'Low participation may indicate students are disengaged or facing barriers',
                'suggested_action': 'Consider: Are class schedules preventing access? Are instructions clear? Try a reminder announcement or check-in with students.',
            })
        
        # Alert: CWI deviation
        if metrics.cwi_deviation_within_20pct < (100 * (1 - self.analytics_policy["cwi_deviation_warning_threshold"])):
            alerts.append({
                'alert_key': 'cwi_deviation',
                'severity': 'warning',
                'what_changed': f'Only {metrics.cwi_deviation_within_20pct:.1f}% of students are tracking expected income',
                'why_it_matters': 'Large deviations suggest economy settings may not match actual behavior',
                'suggested_action': 'Review: Are wages appropriate for attendance patterns? Are expenses too high? Check the Economy Health page.',
            })
        
        # Alert: Velocity drop
        if trends.velocity_trend == 'decreasing':
            alerts.append({
                'alert_key': 'velocity_drop',
                'severity': 'info',
                'what_changed': 'Money velocity is decreasing',
                'why_it_matters': 'Declining activity may indicate students are hoarding or disengaged',
                'suggested_action': 'Consider: Add new store items, host a special event, or review pricing',
            })
        
        # Alert: Budget survival
        if metrics.cwi_value > 0 and metrics.budget_survival_pass_rate < 50:
            alerts.append({
                'alert_key': 'budget_survival_low',
                'severity': 'critical',
                'what_changed': (
                    f'Only {metrics.budget_survival_pass_rate:.1f}% of students can save '
                    'at least 10% of weekly income'
                ),
                'why_it_matters': 'Many students may be struggling to keep up with recurring expenses',
                'suggested_action': 'URGENT: Review rent and expense settings. Consider temporary relief or wage adjustment.',
            })
        
        return alerts
    
    @requires_feat_context("FEAT-ANLY-001")
    def create_snapshot(
        self,
        window_type: str,
        window_start: datetime,
        window_end: datetime,
        is_complete: bool = True
    ) -> AnalyticsWindowView:
        if not self.class_id:
            raise ValueError("AnalyticsEngine requires canonical class_id context.")

        # Compute metrics
        health_metrics = self.compute_system_health(window_start, window_end)
        
        trends = self.compute_trends(health_metrics, None)
        
        # Count transactions
        total_transactions = Transaction.query.filter(
            Transaction.class_id == self.class_id,
            Transaction.timestamp >= window_start,
            Transaction.timestamp < window_end,
            Transaction.is_void.is_(False)
        ).count()
        
        # Calculate average balance (for CWI comparison only, not for ranking)
        students = self._get_enrolled_students()
        from app.services.ledger_service import get_available_balance
        total_balance = sum(
            float(get_available_balance(s.id, self.class_id, 'checking') or 0)
            for s in students
        )
        avg_balance = total_balance / len(students) if students else 0.0
        
        return AnalyticsWindowView(
            window_type=window_type,
            window_start=window_start,
            window_end=window_end,
            participation_rate=health_metrics.participation_rate,
            money_velocity=health_metrics.money_velocity,
            cwi_deviation_within_20pct=health_metrics.cwi_deviation_within_20pct,
            budget_survival_pass_rate=health_metrics.budget_survival_pass_rate,
            cwi_value=health_metrics.cwi_value,
            avg_student_balance=avg_balance,
            balance_trend=trends.balance_trend,
            velocity_trend=trends.velocity_trend,
            participation_trend=trends.participation_trend,
            total_students=health_metrics.total_students,
            active_students=health_metrics.active_students,
            total_transactions=total_transactions,
            computed_at=utc_now(),
            is_complete=is_complete,
        )
    
    def get_or_create_snapshot(
        self,
        window_type: str,
        window_start: datetime,
        window_end: datetime
    ) -> AnalyticsWindowView:
        """Return a canonical in-memory analytics snapshot view."""
        if not self.class_id:
            raise ValueError("AnalyticsEngine requires canonical class_id context.")
        is_complete = window_end <= utc_now()
        return self.create_snapshot(window_type, window_start, window_end, is_complete)

    def get_snapshot_read_only(
        self,
        window_type: str,
        window_start: datetime,
        window_end: datetime,
    ) -> AnalyticsWindowView:
        """Return an in-memory preview without DB writes."""
        if not self.class_id:
            raise ValueError("AnalyticsEngine requires canonical class_id context.")

        health_metrics = self.compute_system_health(window_start, window_end)
        trends = self.compute_trends(health_metrics, None)
        total_transactions = Transaction.query.filter(
            Transaction.class_id == self.class_id,
            Transaction.timestamp >= window_start,
            Transaction.timestamp < window_end,
            Transaction.is_void.is_(False),
        ).count()
        students = self._get_enrolled_students()
        from app.services.ledger_service import get_available_balance
        total_balance = sum(
            float(get_available_balance(s.id, self.class_id, 'checking') or 0)
            for s in students
        )
        avg_balance = total_balance / len(students) if students else 0.0

        return AnalyticsWindowView(
            window_type=window_type,
            window_start=window_start,
            window_end=window_end,
            participation_rate=health_metrics.participation_rate,
            money_velocity=health_metrics.money_velocity,
            cwi_deviation_within_20pct=health_metrics.cwi_deviation_within_20pct,
            budget_survival_pass_rate=health_metrics.budget_survival_pass_rate,
            cwi_value=health_metrics.cwi_value,
            avg_student_balance=avg_balance,
            balance_trend=trends.balance_trend,
            velocity_trend=trends.velocity_trend,
            participation_trend=trends.participation_trend,
            total_students=health_metrics.total_students,
            active_students=health_metrics.active_students,
            total_transactions=total_transactions,
            computed_at=utc_now(),
            is_complete=(window_end <= utc_now()),
        )

