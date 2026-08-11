"""DermAI — Flask application factory and entrypoint.

Run:   python app.py           (or)   flask --app app run --debug
The database tables are created automatically on first run and seeded with demo users.
"""
import os
from flask import Flask, render_template, redirect, jsonify
from config import Config
from extensions import db
from models import User, log


def ensure_database_exists(uri):
    """For MySQL/Postgres, create the target database if it doesn't exist yet.
    (db.create_all() can make TABLES but not the DATABASE itself.)"""
    if uri.startswith("sqlite"):
        return
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine.url import make_url
    url = make_url(uri)
    dbname = url.database
    server = url.set(database=None)              # connect to the server, no db
    eng = create_engine(server)
    with eng.connect() as c:
        c.execute(text("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4" % dbname))
    eng.dispose()
    print(" * Ensured database '%s' exists" % dbname)


def resolve_database_uri(app):
    """Use the configured DB (WAMP MySQL by default). If it cannot be reached,
    fall back to a local SQLite file so the app ALWAYS runs — and say why."""
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite"):
        return uri
    try:
        ensure_database_exists(uri)
        from sqlalchemy import create_engine, text
        eng = create_engine(uri)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))          # real connectivity test
        eng.dispose()
        print(" * Using MySQL: %s" % uri)
        return uri
    except Exception as e:
        fallback = "sqlite:///%s" % os.path.join(app.root_path, "instance", "dermai.db")
        print("\n !! Could NOT connect to MySQL -> %s" % e)
        print(" !! Reason is usually: WAMP not green / wrong root password / wrong port (try 3306) / PyMySQL not installed.")
        print(" !! Falling back to SQLite so the app still runs: %s\n" % fallback)
        return fallback


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["MODELS_DIR"], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = resolve_database_uri(app)
    db.init_app(app)

    from auth import auth_bp
    from api import api_bp
    from admin import admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    # Surface server errors as JSON so the UI shows the real cause (e.g. DB issues)
    @app.errorhandler(500)
    def _err500(e):
        orig = getattr(e, "original_exception", e)
        return jsonify(error="Server error: " + str(orig)), 500

    # ---- page routes (single-page app) ----
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/verify/<token>")
    def verify_page(token):
        u = User.query.filter_by(verify_token=token).first()
        if u:
            u.is_verified = True
            u.verify_token = None
            db.session.commit()
            log(u.id, "VERIFY", "Email verified via link")
            return redirect("/?verified=1")
        return redirect("/?verified=0")

    @app.get("/health")
    def health():
        return jsonify(status="ok",
                       mode=("trained" if os.path.exists(app.config["WEIGHTS_FILE"]) else "rule"))

    with app.app_context():
        db.create_all()
        seed_if_empty()
    return app


def seed_if_empty():
    """Create demo accounts on first run so the app is immediately usable."""
    if User.query.first():
        return
    demo = [
        ("Dr. Asha Perera", "doctor@dermai.lk", "Password@123", "SLMC-29441", "doctor", "Dermatologist"),
        ("Dr. Kasun Silva", "kasun@dermai.lk", "Password@123", "SLMC-28441", "doctor", "General Practitioner"),
        ("System Admin", "admin@dermai.lk", "Password@123", "ADMIN-001", "admin", "Administrator"),
    ]
    for name, email, pw, reg, role, spec in demo:
        u = User(name=name, email=email, slmc_no=reg, role=role,
                 specialization=spec, is_active=True, is_verified=True)
        u.set_password(pw)
        db.session.add(u)
    db.session.commit()
    print(" * Seeded demo users (doctor@dermai.lk / admin@dermai.lk — Password@123)")


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
