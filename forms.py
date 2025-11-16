from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired
from wtforms import HiddenField, TextAreaField, FloatField, SelectField, IntegerField, DateField, BooleanField
from wtforms.validators import Optional

from wtforms import SubmitField


class StoreItemForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    price = FloatField('Price', validators=[DataRequired()])
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
    submit = SubmitField('Save Item')


class AdminSignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    invite_code = StringField('Invite Code', validators=[DataRequired()])

class AdminTOTPConfirmForm(FlaskForm):
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
    username = HiddenField(validators=[DataRequired()])

    invite_code = HiddenField(validators=[DataRequired()])

class SystemAdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
    submit = SubmitField('Login')
class SystemAdminInviteForm(FlaskForm):
    code = StringField('Custom Code')
    expiry_days = StringField('Expiry Days')
    expires_at = StringField('Expires At')  # Added to match app.py usage
    submit = SubmitField('Generate Invite Code')

class StudentClaimAccountForm(FlaskForm):
    first_half = StringField('First Half', validators=[DataRequired()])
    second_half = StringField('Second Half', validators=[DataRequired()])
    submit = SubmitField('Claim Account')

class StudentCreateUsernameForm(FlaskForm):
    write_in_word = StringField('Your Word', validators=[DataRequired()])
    submit = SubmitField('Generate Username')

class StudentPinPassphraseForm(FlaskForm):
    pin = StringField('PIN', validators=[DataRequired()])
    passphrase = StringField('Passphrase', validators=[DataRequired()])
    submit = SubmitField('Finish Setup')

class StudentLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    pin = StringField('PIN', validators=[DataRequired()])
    submit = SubmitField('Login')

class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
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
    waiting_period_days = IntegerField('Waiting Period (days)', default=7, validators=[DataRequired()])
    max_claims_count = IntegerField('Max Claims per Period (leave blank for unlimited)', validators=[Optional()])
    max_claims_period = SelectField('Claims Period', choices=[
        ('month', 'Per Month'),
        ('semester', 'Per Semester'),
        ('year', 'Per Year')
    ], default='month')
    max_claim_amount = FloatField('Max Claim Amount $ (leave blank for unlimited)', validators=[Optional()])

    # Claim type
    is_monetary = BooleanField('Monetary Claims (students claim dollar amounts)', default=True)

    # Special rules
    no_repurchase_after_cancel = BooleanField('Prevent repurchase after cancellation', default=False)
    repurchase_wait_days = IntegerField('Days to wait before repurchase', default=30)
    auto_cancel_nonpay_days = IntegerField('Auto-cancel after days of non-payment', default=7)
    claim_time_limit_days = IntegerField('Time limit to file claim (days from incident)', default=30)

    # Bundle settings
    bundle_discount_percent = FloatField('Bundle Discount %', default=0, validators=[Optional()])

    is_active = BooleanField('Policy is Active', default=True)
    submit = SubmitField('Save Policy')


class InsuranceClaimForm(FlaskForm):
    policy_id = SelectField('Insurance Policy', coerce=int, validators=[DataRequired()])
    incident_date = DateField('Date of Incident', format='%Y-%m-%d', validators=[DataRequired()])
    description = TextAreaField('Claim Description', validators=[DataRequired()])
    claim_amount = FloatField('Claim Amount ($)', validators=[Optional()])
    claim_item = StringField('What are you claiming?', validators=[Optional()])
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