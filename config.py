import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'jj-hospital-secret-key-change-in-production-2026')

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'neon_db_connection_string',
        'sqlite:///' + os.path.join(BASE_DIR, 'jj_hospital.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('gmail_id', '')
    MAIL_PASSWORD = os.environ.get('gmail_password', '')
    MAIL_RECIPIENT = os.environ.get('mail_recipient', '')
