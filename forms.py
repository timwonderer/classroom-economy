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
        ('collective', 'Collective Goal')
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
    dob_sum = StringField('DOB Sum', validators=[DataRequired()])
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