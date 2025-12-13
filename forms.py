from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, ValidationError, Length
from wtforms import HiddenField, TextAreaField, FloatField, SelectField, IntegerField, DateField, BooleanField, SelectMultipleField
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
    invite_code = StringField('Invite Code', validators=[DataRequired()])
    dob_sum = StringField('Date of Birth Sum (MM+DD+YYYY)', validators=[DataRequired()])

class AdminTOTPConfirmForm(FlaskForm):
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
    username = HiddenField(validators=[DataRequired()])
    dob_sum = HiddenField(validators=[DataRequired()])
    invite_code = HiddenField(validators=[DataRequired()])

class AdminRecoveryForm(FlaskForm):
    student_usernames = StringField('Student Usernames (comma-separated, one from each class)', validators=[DataRequired()])
    dob_sum = StringField('Date of Birth Sum (MM+DD+YYYY)', validators=[DataRequired()])
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
    first_initial = StringField('First Initial (e.g., J)', validators=[DataRequired(), Length(min=1, max=1)])
    last_name = StringField('Last Name', validators=[DataRequired()])
    dob_sum = StringField('DOB Sum (MM + DD + YYYY)', validators=[DataRequired()])
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


# -------------------- INSURANCE FORMS --------------------
class InsurancePolicyForm(FlaskForm):
    title = StringField('Policy Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    premium = FloatField('Monthly Premium ($)', validators=[DataRequired()])
    charge_frequency = SelectField('Charge Frequency', choices=[
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('semester', 'Per Semester')
    ], default='monthly')
    autopay = BooleanField('Enable Autopay', default=True)
    claim_type = SelectField(
        'Claim Type',
        choices=[
            ('transaction_monetary', 'Transactions-based (linked to spending)'),
            ('non_monetary', 'Non-monetary (no reimbursement)'),
            ('legacy_monetary', 'Legacy monetary (manual amount)'),
        ],
        default='transaction_monetary',
    )
    waiting_period_days = IntegerField('Waiting Period (days)', default=7, validators=[DataRequired()])
    max_claims_count = IntegerField('Max Claims per Period (leave blank for unlimited)', validators=[Optional()])
    max_claims_period = SelectField('Claims Period', choices=[
        ('month', 'Per Month'),
        ('semester', 'Per Semester'),
        ('year', 'Per Year')
    ], default='month')
    max_claim_amount = FloatField('Max Claim Amount $ (leave blank for unlimited)', validators=[Optional()])
    max_payout_per_period = FloatField('Max Total Payout per Period $ (leave blank for unlimited)', validators=[Optional()])

    # Special rules
    no_repurchase_after_cancel = BooleanField('Prevent repurchase after cancellation (permanent block)', default=False)
    enable_repurchase_cooldown = BooleanField('Enable forced cooldown period', default=False)
    repurchase_wait_days = IntegerField('Cooldown days before repurchase allowed', default=30)
    auto_cancel_nonpay_days = IntegerField('Auto-cancel after days of non-payment', default=7)
    claim_time_limit_days = IntegerField('Time limit to file claim (days from incident)', default=30)

    # Bundle settings
    bundle_with_policy_ids = StringField('Bundle with Policies', validators=[Optional()])  # Comma-separated IDs
    bundle_discount_percent = FloatField('Bundle Discount %', default=0, validators=[Optional()])
    bundle_discount_amount = FloatField('Bundle Discount Amount ($)', default=0, validators=[Optional()])

    # Marketing badge
    marketing_badge = SelectField('Marketing Badge (optional)', choices=[
        ('', 'None'),
        ('best_value', 'Best Value!'),
        ('most_popular', 'Most Popular'),
        ('recommended', 'Recommended'),
        ('premium', 'Premium Coverage'),
        ('limited_time', 'Limited Time Offer'),
        ('new', 'New!'),
        ('fan_favorite', 'Fan Favorite'),
        ('yolo', 'YOLO Protection'),
        ('trust_me', 'Trust Me Bro'),
        ('definitely_not_scam', 'Definitely Not a Scam'),
        ('parents_approved', 'Your Parents Would Approve'),
        ('as_seen_on_tv', 'As Seen on TV'),
        ('industry_leading', 'Industry Leading*'),
        ('chaos_insurance', 'Chaos Insurance'),
        ('responsible_choice', 'The Responsible Choice™'),
        ('your_friend_has_it', 'The One Your Friend Has')
    ], validators=[Optional()])

    # Tier/Category settings
    tier_category_id = IntegerField('Tier Category ID (for grouping)', validators=[Optional()])
    tier_name = StringField('Tier Name (e.g., "Paycheck Protection")', validators=[Optional()])
    tier_color = SelectField('Tier Color Theme', choices=[
        ('', 'None'),
        ('primary', 'Blue (Primary)'),
        ('success', 'Green (Success)'),
        ('info', 'Cyan (Info)'),
        ('warning', 'Yellow (Warning)'),
        ('danger', 'Red (Danger)'),
        ('secondary', 'Gray (Secondary)'),
        ('dark', 'Dark')
    ], validators=[Optional()])

    # Settings mode
    settings_mode = SelectField('Settings Mode', choices=[
        ('simple', 'Simple'),
        ('advanced', 'Advanced')
    ], default='advanced')

    is_active = BooleanField('Policy is Active', default=True)
    blocks = SelectMultipleField('Visible to Periods/Blocks (leave empty for all)', choices=[], validators=[Optional()])
    submit = SubmitField('Save Policy')


class InsuranceClaimForm(FlaskForm):
    incident_date = DateField('Date of Incident', format='%Y-%m-%d', validators=[DataRequired()])
    description = TextAreaField('Claim Description', validators=[DataRequired()])
    claim_amount = FloatField('Claim Amount ($)', validators=[Optional()])
    claim_item = StringField('What are you claiming?', validators=[Optional()])
    transaction_id = SelectField('Transaction', coerce=int, validators=[Optional()])
    comments = TextAreaField('Additional Comments (optional)', validators=[Optional()])
    submit = SubmitField('Submit Claim')


class AdminClaimProcessForm(FlaskForm):
    status = SelectField('Status', choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid')
    ], validators=[DataRequired()])
    approved_amount = FloatField('Approved Amount', validators=[Optional()])
    rejection_reason = TextAreaField('Rejection Reason (if rejected)')
    admin_notes = TextAreaField('Admin Notes')
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


class PayrollRewardForm(FlaskForm):
    name = StringField('Reward Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    amount = FloatField('Amount ($)', validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Reward')


class PayrollFineForm(FlaskForm):
    name = StringField('Fine Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    amount = FloatField('Amount ($)', validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Fine')


class ManualPaymentForm(FlaskForm):
    description = StringField('Payment Description', validators=[DataRequired()])
    amount = FloatField('Amount ($)', validators=[DataRequired()])
    account_type = SelectField('Account Type', choices=[
        ('checking', 'Checking'),
        ('savings', 'Savings')
    ], default='checking', validators=[DataRequired()])
    # student_ids will be handled in the template with checkboxes
    submit = SubmitField('Send Payment')


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
    """Form for logged-in students to add a new class by entering a join code."""
    join_code = StringField('Join Code (from your teacher)', validators=[DataRequired()])
    first_initial = StringField('First Initial (e.g., J)', validators=[DataRequired(), Length(min=1, max=1)])
    last_name = StringField('Last Name', validators=[DataRequired()])
    dob_sum = StringField('DOB Sum (MM + DD + YYYY)', validators=[DataRequired()])
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