from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired
from wtforms import HiddenField

from wtforms import SubmitField


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