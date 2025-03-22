import os
from flask import Flask, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    jwt.init_app(app)

    # --- CORS CONFIGURATION ---
    CORS(app,
         resources={r"/*": {"origins": [app.config.get("FRONTEND_URL", "*")]}},
         supports_credentials=True,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"]
    )

    # --- HANDLE OPTIONS Preflight Explicitly (just in case) ---
    @app.after_request
    def after_request(response):
        origin = request.headers.get("Origin")
        if origin and origin == app.config.get("FRONTEND_URL"):
            response.headers.add("Access-Control-Allow-Origin", origin)
        else:
            response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS,PUT,DELETE")
        return response

    # --- Register your routes ---
    from app.routes import main
    app.register_blueprint(main)

    return app
