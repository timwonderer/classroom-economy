from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired
from wtforms import HiddenField

class AdminSignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    invite_code = StringField('Invite Code', validators=[DataRequired()])

class AdminTOTPConfirmForm(FlaskForm):
    totp_code = StringField('TOTP Code', validators=[DataRequired()])
    username = HiddenField(validators=[DataRequired()])
    invite_code = HiddenField(validators=[DataRequired()])