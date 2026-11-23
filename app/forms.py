from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FloatField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Optional
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[
        DataRequired(message="Email is required."),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required.")
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[
        DataRequired(message="Full name is required."),
        Length(min=2, max=100, message="Name must be between 2 and 100 characters.")
    ])
    email = StringField('Email Address', validators=[
        DataRequired(message="Email is required."),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required."),
        Length(min=8, message="Password must be at least 8 characters long.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo('password', message="Passwords must match.")
    ])
    submit = SubmitField('Create Account')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError("An account with this email address already exists.")


class TransactionAnalysisForm(FlaskForm):
    amount = FloatField('Transaction Amount ($)', validators=[
        DataRequired(message="Amount is required."),
        NumberRange(min=0.01, max=10000000.0, message="Amount must be greater than 0.")
    ], default=250.00)

    transaction_type = SelectField('Transaction Type', choices=[
        ('Transfer', 'Transfer'),
        ('Payment', 'Payment'),
        ('Cash Withdrawal', 'Cash Withdrawal'),
        ('Deposit', 'Deposit'),
        ('Purchase', 'Purchase')
    ], validators=[DataRequired()])

    sender_account = StringField('Sender Account ID', validators=[
        DataRequired(message="Sender Account is required."),
        Length(min=3, max=64)
    ], default='ACC-ORIG-10924')

    receiver_account = StringField('Receiver Account ID', validators=[
        DataRequired(message="Receiver Account is required."),
        Length(min=3, max=64)
    ], default='ACC-DEST-88319')

    channel = SelectField('Transaction Channel', choices=[
        ('Mobile Banking', 'Mobile Banking'),
        ('Internet Banking', 'Internet Banking'),
        ('ATM', 'ATM'),
        ('POS', 'POS Terminal'),
        ('UPI', 'UPI')
    ], validators=[DataRequired()])

    location = SelectField('Transaction Location', choices=[
        ('Domestic', 'Domestic (Primary Residence City)'),
        ('High-Risk Domestic', 'High-Risk Domestic (New Region)'),
        ('Cross-Border (Recognized)', 'Cross-Border (Frequent Destination)'),
        ('Cross-Border (Unusual)', 'Cross-Border (Flagged / High-Risk)')
    ], validators=[DataRequired()])

    device = SelectField('Device Information', choices=[
        ('Mobile App (Recognized)', 'Mobile App (Registered Device)'),
        ('Web Browser (Recognized)', 'Web Browser (Recognized Session)'),
        ('New / Unrecognized Device', 'New / Unrecognized Device'),
        ('ATM Terminal', 'ATM Terminal'),
        ('POS Terminal', 'POS Terminal')
    ], validators=[DataRequired()])

    frequency_24h = IntegerField('Transactions in Past 24h', validators=[
        DataRequired(message="Frequency is required."),
        NumberRange(min=0, max=500, message="Frequency must be non-negative.")
    ], default=2)

    account_age_days = IntegerField('Account Age (Days)', validators=[
        DataRequired(message="Account age is required."),
        NumberRange(min=0, max=15000, message="Account age must be non-negative.")
    ], default=365)

    previous_amount = FloatField('Previous Transaction Amount ($)', validators=[
        DataRequired(message="Previous amount is required."),
        NumberRange(min=0.0, max=10000000.0, message="Previous amount must be non-negative.")
    ], default=180.00)

    submit = SubmitField('Analyze Transaction')


class BatchUploadForm(FlaskForm):
    csv_file = FileField('Upload Transaction CSV File', validators=[
        FileRequired(message="Please select a CSV file to upload."),
        FileAllowed(['csv'], message="Only .csv files are supported.")
    ])
    submit = SubmitField('Upload and Analyze Batch')


class UpdateProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[
        DataRequired(message="Full name is required."),
        Length(min=2, max=100)
    ])
    current_password = PasswordField('Current Password (Required for password change)', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[
        Optional(),
        Length(min=8, message="New password must be at least 8 characters long.")
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        EqualTo('new_password', message="New passwords must match.")
    ])
    submit = SubmitField('Save Profile Changes')
