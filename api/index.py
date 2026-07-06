import sys
import os

# Make sure the root project directory is on the Python path
# so that app.py and templates/static can be found correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402  (app is the Flask instance)

# Vercel looks for a variable named `app` in this file
