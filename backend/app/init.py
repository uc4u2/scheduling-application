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

    # Clean and proper CORS configuration
    CORS(app,
         resources={r"/*": {"origins": [app.config.get("FRONTEND_URL", "https://scheduling-frontend.onrender.com/")]}},
         supports_credentials=True,
         expose_headers=["Content-Type", "Authorization"]
    )

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)

    return app

