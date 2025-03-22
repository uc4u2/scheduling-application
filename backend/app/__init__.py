import os
import shutil
from flask import Flask, send_file
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

    # ✅ CORS with correct frontend origin
    CORS(app, 
         resources={r"/*": {"origins": [app.config["FRONTEND_URL"]]}},
         supports_credentials=True,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization"]
    )

    # Register routes
    from app.routes import main
    app.register_blueprint(main)

    # ✅ TEMP: Route to download zipped backend
    @app.route("/download-backend")
    def download_backend():
        zip_path = "/tmp/backend.zip"
        source_dir = "/opt/render/project/src"
        shutil.make_archive(zip_path.replace(".zip", ""), "zip", source_dir)
        return send_file(zip_path, as_attachment=True)

    return app
