import json
from itertools import groupby
from uuid import uuid4
from bson.objectid import ObjectId
from flask import Flask, request, session, abort, Response
from flask import render_template, url_for, jsonify
from flask.ext.babel import Babel
from flask.ext.mail import Mail
from flask.ext.pymongo import PyMongo
from flask.ext.sqlalchemy import SQLAlchemy
from flaskext.markdown import Markdown
from flask.ext.user import current_user, login_required, UserManager, UserMixin, SQLAlchemyAdapter
from flask_wtf.csrf import CsrfProtect
from pymongo.errors import ConnectionFailure

from gears_less import LESSCompiler
from gears_coffeescript import CoffeeScriptCompiler

#Comment out this block if you run this file directly. (Strictly for development purposes only)
from .flask_gears import Gears
from .sessions import MongoSessionInterface

#For running this file directly uncomment this and comment the block above it.
#from flask_gears import Gears
#from sessions import MongoSessionInterface
#from settings import MONGO_DBNAME, SECRET_KEY, DEBUG_MODE

from hpit.management.settings_manager import SettingsManager
settings = SettingsManager.get_server_settings()

class ServerApp:
    instance = None

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = ServerApp()

        return cls.instance

    def __init__(self):
        if self.instance:
            raise ValueError("ServerApp instance already created.")

        self.gears = Gears(
            compilers={
            '.less': LESSCompiler.as_handler(),
            '.coffee': CoffeeScriptCompiler.as_handler(),
            #    '.hbs': 'gears_handlebars.HandlebarsCompiler'
            }
        )

        self.app = Flask(__name__)
        self.gears.init_app(self.app)

        self.app.config.from_object(settings)
        
        import logging
        from logging.handlers import RotatingFileHandler
        log_handler = RotatingFileHandler("log/app.log",maxBytes = 10000000, backupCount = 1) #10mb
        log_handler.setLevel(logging.DEBUG)
        self.app.logger.addHandler(log_handler)

        try:
            self.mongo = PyMongo(self.app)
            #self.app.session_interface = MongoSessionInterface(self.app, self.mongo)
        except ConnectionFailure:
            self.mongo = None

        self.babel = Babel(self.app)
        self.db = SQLAlchemy(self.app)
        self.mail = Mail(self.app)
        self.md = Markdown(self.app)
        self.csrf = CsrfProtect(self.app)

        self.user_bootstrapped = False


    def bootstrap_user(self):
        if not self.user_bootstrapped:
            from .models import User
            self.db_adapter = SQLAlchemyAdapter(self.db, User)
            self.user_manager = UserManager(self.db_adapter, self.app)
            self.user_bootstrapped = True
