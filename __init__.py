from flask import Flask


# from models import db
from routes.main_blueprint import main_bp
from routes.service_blueprint import ldap_bp




def create_app():
    app = Flask(__name__)
    app.register_blueprint(main_bp)
    app.register_blueprint(ldap_bp)
    app.config.from_pyfile('config.py') # call configuration from Congifg.py
    # db.init_app(app)  # Initialize sqlite database
    # with app.app_context():
        # db.create_all() #create all data of models,create database

    return app
