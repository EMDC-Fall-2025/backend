# emdcbackend/settings_sqlite.py
from .settings import *        # keep INSTALLED_APPS (includes django.contrib.auth)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "sqlite3.db",  # or your actual sqlite file
    }
}
