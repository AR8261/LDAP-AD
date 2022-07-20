"""Flask configuration"""
#Here I configure flask sqlalchemy
import os

# SQLALCHEMY_DATABASE_URI= 'sqlite:///student.db'
# SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = os.urandom(24)
# DEBUG = True
