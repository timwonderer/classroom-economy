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