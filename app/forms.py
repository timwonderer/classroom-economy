from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, ValidationError, Length
from wtforms import HiddenField, TextAreaField, FloatField, SelectField, IntegerField, DateField, BooleanField, SelectMultipleField, RadioField
from wtforms.validators import Optional

from wtforms import SubmitField


class StoreItemForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    price = FloatField('Price', validators=[DataRequired()])
    tier = SelectField('Pricing Tier (optional)', choices=[
        ('', 'No Tier'),
        ('basic', 'Basic (2-5% of CWI)'),
        ('standard', 'Standard (5-10% of CWI)'),
        ('premium', 'Premium (10-25% of CWI)'),
        ('luxury', 'Luxury (25-50% of CWI)')
    ], validators=[Optional()])
    item_type = SelectField('Item Type', choices=[
        ('immediate', 'Immediate Use'),
        ('delayed', 'Delayed Use'),
        ('collective', 'Collective Goal'),
        ('hall_pass', 'Hall Pass')
    ], validators=[DataRequired()])
    inventory = IntegerField('Inventory (leave blank for unlimited)', validators=[Optional()])
    limit_per_student = IntegerField('Purchase Limit per Student (leave blank for no limit)', validators=[Optional()])
    auto_delist_date = DateField('Auto-Delist Date (optional)', format='%Y-%m-%d', validators=[Optional()])
    auto_expiry_days = IntegerField('Item Expiry in Days (optional, for delayed-use items)', validators=[Optional()])
    is_active = BooleanField('Item is Active', default=True)
    is_long_term_goal = BooleanField('Long-Term Goal Item (exclude from CWI balance checks)', default=False)
    bypass_cwi_warnings = BooleanField('Bypass CWI Warnings', default=False)
    blocks = SelectMultipleField('Visible to Periods/Blocks (leave empty for all)', choices=[], validators=[Optional()])

    # Bundle settings
    is_bundle = BooleanField('This is a Bundled Item', default=False)
    bundle_quantity = IntegerField('Bundle Quantity (number of items in bundle)', validators=[Optional()])

    # Bulk discount settings
    bulk_discount_enabled = BooleanField('Enable Bulk Discount', default=False)
    bulk_discount_quantity = IntegerField('Minimum Quantity for Discount', validators=[Optional()])
    bulk_discount_percentage = FloatField('Discount Percentage (%)', validators=[Optional()])

    # Collective goal settings (only for item_type='collective')
    collective_goal_type = SelectField('Collective Goal Type', choices=[
        ('', 'Select Type'),
        ('fixed', 'Fixed Number of Purchases'),
        ('whole_class', 'Whole Class Must Purchase (1 per person)')
    ], validators=[Optional()])
    collective_goal_target = IntegerField('Target Number of Purchases (for Fixed type)', validators=[Optional()])
    collective_goal_expires_at = DateField('Goal Expiration Date (optional)', format='%Y-%m-%d', validators=[Optional()])

    # Redemption settings (for delayed-use items)
    redemption_prompt = TextAreaField('Redemption Prompt (optional, for delayed-use items)', validators=[Optional()])

    submit = SubmitField('Save Item')

    def validate_bundle_quantity(self, field):
        """Validate bundle quantity when bundle is enabled."""
        if self.is_bundle.data and (not field.data or field.data <= 0):
            raise ValidationError('Bundle quantity is required and must be greater than 0 when creating a bundled item.')

    def validate_bulk_discount_quantity(self, field):
        """Validate bulk discount quantity when bulk discount is enabled."""
        if self.bulk_discount_enabled.data and (not field.data or field.data <= 0):
            raise ValidationError('Minimum quantity is required and must be greater than 0 when bulk discount is enabled.')

    def validate_bulk_discount_percentage(self, field):
        """Validate bulk discount percentage when bulk discount is enabled."""
        if self.bulk_discount_enabled.data:
            if not field.data or field.data <= 0:
                raise ValidationError('Discount percentage is required and must be greater than 0 when bulk discount is enabled.')
            if field.data > 100:
                raise ValidationError('Discount percentage cannot exceed 100%.')

    def validate_collective_goal_type(self, field):
        """Validate collective goal type is set when item type is collective."""
        if self.item_type.data == 'collective' and not field.data:
            raise ValidationError('Collective goal type is required when item type is Collective Goal.')

    def validate_collective_goal_target(self, field):
        """Validate collective goal target when type is fixed."""
        if self.item_type.data == 'collective' and self.collective_goal_type.data == 'fixed':
            if not field.data or field.data <= 0:
                raise ValidationError('Target number of purchases is required and must be greater than 0 when using Fixed collective goal type.')


class AdminSignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    turnstile_token = HiddenField('cf-turnstile-response')

class AdminTOTPConfirmForm(FlaskForm):
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
    username = HiddenField(validators=[DataRequired()])

class AdminRecoveryForm(FlaskForm):
    """Recovery form — join_code[]/student_username[] pairs are submitted as arrays.
    This form only provides CSRF protection; no WTForms fields for the pair data."""
    submit = SubmitField('Verify Identity')

class AdminResetCredentialsForm(FlaskForm):
    # recovery_code fields are handled dynamically in the template
    new_username = StringField('New Username', validators=[DataRequired()])
    submit = SubmitField('Reset Account')

class SystemAdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
    turnstile_token = HiddenField('cf-turnstile-response')
    submit = SubmitField('Login')
class SystemAdminInviteForm(FlaskForm):
    code = StringField('Custom Code')
    expiry_days = StringField('Expiry Days')
    expires_at = StringField('Expires At')  # Added to match app.py usage
    submit = SubmitField('Generate Invite Code')

class StudentClaimAccountForm(FlaskForm):
    join_code = StringField('Join Code (from your teacher)', validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=128)])
    last_name = StringField('Last Name', validators=[DataRequired()])
    dedupe_code = StringField('Deduplication Code (if provided by teacher)', validators=[Optional(), Length(max=32)])
    submit = SubmitField('Claim Account')

class StudentCreateUsernameForm(FlaskForm):
    write_in_word = StringField('Your Word', validators=[DataRequired()])
    submit = SubmitField('Generate Username')

class StudentPinPassphraseForm(FlaskForm):
    pin = PasswordField('PIN', validators=[DataRequired()])
    passphrase = PasswordField('Passphrase', validators=[DataRequired()])
    submit = SubmitField('Finish Setup')

class StudentLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    pin = PasswordField('PIN', validators=[DataRequired()])
    turnstile_token = HiddenField('cf-turnstile-response')
    submit = SubmitField('Login')

class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
    turnstile_token = HiddenField('cf-turnstile-response')
    submit = SubmitField('Log In')


class AdminClaimProcessForm(FlaskForm):
    status = SelectField('Status', choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid')
    ], validators=[DataRequired()])
    approved_amount = FloatField('Approved Amount', validators=[Optional()])
    rejection_reason = TextAreaField('Rejection Reason (if rejected)')
    teacher_notes = TextAreaField('Teacher Notes')
    submit = SubmitField('Update Claim')


# -------------------- PAYROLL FORMS --------------------
class PayrollSettingsForm(FlaskForm):
    block = SelectField('Class Block/Period', choices=[], validators=[Optional()])  # Empty choices, populated dynamically
    pay_rate = FloatField('Pay Rate ($ per minute)', validators=[DataRequired()], default=0.25)
    payroll_frequency_days = IntegerField('Payroll Frequency (days)', validators=[DataRequired()], default=14)
    overtime_multiplier = FloatField('Overtime Multiplier', validators=[Optional()], default=1.0)
    bonus_rate = FloatField('Bonus Rate ($ per minute)', validators=[Optional()], default=0.0)
    apply_to_all = BooleanField('Apply to All Blocks', default=False)
    is_active = BooleanField('Settings Active', default=True)
    submit = SubmitField('Save Settings')


class ManualPaymentForm(FlaskForm):
    saved_adjustment_id = HiddenField('Saved Adjustment ID', validators=[Optional()])
    action_type = HiddenField('Action Type', default='apply')
    description = StringField('Payment Description', validators=[DataRequired()])
    is_deposit = RadioField('Type', choices=[
        ('True', 'Deposit (+)'),
        ('False', 'Deduction (-)')
    ], default='True', validators=[DataRequired()])
    amount = FloatField('Amount ($)', validators=[DataRequired()])
    account_type = SelectField('Account Type', choices=[
        ('checking', 'Checking'),
        ('savings', 'Savings')
    ], default='checking', validators=[DataRequired()])
    # student_ids will be handled in the template with checkboxes
    submit = SubmitField('Apply')


# -------------------- BANKING FORMS --------------------
class BankingSettingsForm(FlaskForm):
    # Interest settings
    rate_input_mode = SelectField('Interest Rate Input Mode', choices=[
        ('apy', 'Annual Percentage Yield (APY)'),
        ('monthly', 'Monthly Interest Rate')
    ], default='apy')
    savings_apy = FloatField('Annual Percentage Yield (APY %)', validators=[Optional()], default=0.0)
    savings_monthly_rate = FloatField('Monthly Interest Rate (%)', validators=[Optional()], default=0.0)
    interest_calculation_type = SelectField('Interest Calculation Type', choices=[
        ('simple', 'Simple Interest'),
        ('compound', 'Compound Interest')
    ], default='simple', validators=[DataRequired()])
    compound_frequency = SelectField('Compounding Frequency', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ], default='monthly', validators=[Optional()])

    # Interest payout schedule
    interest_schedule_type = SelectField('Interest Payout Schedule', choices=[
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly (30 day cycle)')
    ], default='monthly', validators=[DataRequired()])
    interest_schedule_cycle_days = IntegerField('Cycle Days (for monthly)', default=30, validators=[Optional()])
    interest_payout_start_date = DateField('Starting Date', format='%Y-%m-%d', validators=[Optional()])

    # Overdraft protection
    overdraft_protection_enabled = BooleanField('Enable Overdraft Protection (Savings covers Checking)', default=False)

    # Overdraft fees
    overdraft_fee_enabled = BooleanField('Enable Overdraft/NSF Fees', default=False)
    overdraft_fee_type = SelectField('Fee Type', choices=[
        ('flat', 'Flat Fee per Transaction'),
        ('progressive', 'Progressive Fee per Transaction')
    ], default='flat')
    overdraft_fee_flat_amount = FloatField('Flat Fee Amount ($)', default=0.0, validators=[Optional()])

    # Progressive fee tiers
    overdraft_fee_progressive_1 = FloatField('1st Overdraft Fee ($)', default=0.0, validators=[Optional()])
    overdraft_fee_progressive_2 = FloatField('2nd Overdraft Fee ($)', default=0.0, validators=[Optional()])
    overdraft_fee_progressive_3 = FloatField('3rd+ Overdraft Fee ($)', default=0.0, validators=[Optional()])
    overdraft_fee_progressive_cap = FloatField('Fee Cap per Period ($, optional)', validators=[Optional()])

    submit = SubmitField('Save Banking Settings')


class StudentAddClassForm(FlaskForm):
    """Form for logged-in students to add a new class by entering a join code.

    join_code is ingress/display metadata only; the boundary must resolve it
    to class_id before any class-scoped work proceeds.
    """
    join_code = StringField('Join Code (from your teacher)', validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=128)])
    last_name = StringField('Last Name', validators=[DataRequired()])
    dedupe_code = StringField('Deduplication Code (if provided by teacher)', validators=[Optional(), Length(max=32)])
    submit = SubmitField('Add Class')


class StudentCompleteProfileForm(FlaskForm):
    """Form for legacy students to complete their profile with missing information."""
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=100)])
    dob_month = SelectField('Birth Month', choices=[
        ('', 'Select Month'),
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], validators=[DataRequired()])
    dob_day = StringField('Day (1-31)', validators=[DataRequired(), Length(min=1, max=2)])
    dob_year = StringField('Year (4 digits)', validators=[DataRequired(), Length(min=4, max=4)])
    submit = SubmitField('Complete Profile')


# -------------------- ANNOUNCEMENT FORMS --------------------
class AnnouncementForm(FlaskForm):
    """Form for creating and editing teacher class announcements."""
    class_id = HiddenField('Class ID', validators=[DataRequired()])
    title = StringField('Announcement Title', validators=[DataRequired(), Length(min=1, max=200)])
    message = TextAreaField('Message', validators=[DataRequired()])
    priority = SelectField('Priority', choices=[
        ('low', 'Low - General Information'),
        ('normal', 'Normal - Standard Announcement'),
        ('high', 'High - Important Notice'),
        ('urgent', 'Urgent - Critical Alert')
    ], default='normal', validators=[DataRequired()])
    is_active = BooleanField('Display to Students', default=True)
    expires_at = DateField('Expiration Date (optional)', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Save Announcement')


class SystemAdminAnnouncementForm(FlaskForm):
    """Form for creating system-wide announcements."""
    audience_type = SelectField('Audience', choices=[
        ('system_wide', 'Everyone (System-Wide)'),
        ('all_students', 'All Students'),
        ('all_teachers', 'All Teachers'),
        ('teacher_all_classes', 'All Classes of Specific Teacher')
    ], validators=[DataRequired()])

    # Custom coerce function to handle empty string (when "-- Select Teacher --" is chosen)
    @staticmethod
    def _coerce_teacher_id(value):
        """Coerce teacher ID, treating empty string as None."""
        if value == '' or value is None:
            return None
        return int(value)

    target_teacher = SelectField('Target Teacher', choices=[], validators=[Optional()], coerce=_coerce_teacher_id)
    title = StringField('Announcement Title', validators=[DataRequired(), Length(min=1, max=200)])
    message = TextAreaField('Message', validators=[DataRequired()])
    priority = SelectField('Priority', choices=[
        ('low', 'Low - General Information'),
        ('normal', 'Normal - Standard Announcement'),
        ('high', 'High - Important Notice'),
        ('urgent', 'Urgent - Critical Alert')
    ], default='normal', validators=[DataRequired()])
    is_active = BooleanField('Display Immediately', default=True)
    expires_at = DateField('Expiration Date (optional)', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Post Announcement')


# ---- Issue Resolution Forms ----

class StudentIssueSubmissionForm(FlaskForm):
    """Form for students to submit general (non-transaction) issues."""
    category_id = SelectField('Issue Type', coerce=int, validators=[DataRequired(message="Please select an issue type.")])
    explanation = TextAreaField('What happened?', validators=[
        DataRequired(message="Please describe what happened."),
        Length(max=1000, message="Description must be 1000 characters or less.")
    ])
    expected_outcome = TextAreaField('What did you expect to happen?', validators=[
        Optional(),
        Length(max=500, message="Expected outcome must be 500 characters or less.")
    ])
    submit = SubmitField('Submit Issue')


class TransactionIssueSubmissionForm(FlaskForm):
    """Form for students to report transaction-specific issues."""
    category_id = SelectField('Issue Type', coerce=int, validators=[DataRequired(message="Please select an issue type.")])
    explanation = TextAreaField('What\'s wrong with this transaction?', validators=[
        DataRequired(message="Please explain the issue."),
        Length(max=1000, message="Explanation must be 1000 characters or less.")
    ])
    expected_outcome = TextAreaField('What should it be instead?', validators=[
        Optional(),
        Length(max=500, message="Expected outcome must be 500 characters or less.")
    ])
    submit = SubmitField('Submit Issue')
