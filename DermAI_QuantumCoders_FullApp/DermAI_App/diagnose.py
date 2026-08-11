"""Run:  python diagnose.py
Prints, in plain English, exactly what is (or isn't) working."""
import sys
print("="*60)
print("DermAI diagnostic")
print("="*60)
print("Python:", sys.version.split()[0])

try:
    import pymysql; print("[OK]  PyMySQL is installed")
except Exception as e:
    print("[X ]  PyMySQL NOT installed  ->  run:  pip install PyMySQL")

from config import Config
uri = Config.SQLALCHEMY_DATABASE_URI
print("Configured database:", uri)

if uri.startswith("mysql"):
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine.url import make_url
        u = make_url(uri)
        # 1) connect to server (no db)
        eng = create_engine(u.set(database=None))
        with eng.connect() as c:
            c.execute(text("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4" % u.database))
        eng.dispose()
        print("[OK]  Connected to MySQL server and ensured database '%s'" % u.database)
        # 2) connect to the db
        eng = create_engine(uri)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        eng.dispose()
        print("[OK]  Connected to database '%s'" % u.database)
    except Exception as e:
        print("[X ]  MySQL connection FAILED:")
        print("      ", e)
        print("      Fix: WAMP green? root password? port 3306/3308? PyMySQL installed?")

# 3) build tables + seed + test login
try:
    from app import app
    from extensions import db
    from models import User
    with app.app_context():
        print("Actually using:", app.config["SQLALCHEMY_DATABASE_URI"])
        print("Users in DB:", User.query.count())
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email":"doctor@dermai.lk","password":"Password@123"})
    print("Test login status:", r.status_code, "->", r.get_json())
    if r.status_code == 200:
        print("\n[RESULT] LOGIN WORKS. If the browser still fails, hard-refresh (Ctrl+Shift+R).")
    else:
        print("\n[RESULT] Login returned", r.status_code, "- see message above.")
except Exception as e:
    import traceback; traceback.print_exc()
    print("\n[RESULT] App failed to start:", e)
print("="*60)
