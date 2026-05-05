# wsgi.py - For production with gunicorn
from app import app

if __name__ == "__main__":
    app.run()