import os

class Config:
    """Application configuration"""
    SQLALCHEMY_DATABASE_URI = 'sqlite:///chat_app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
