import os


DATABASE_URL = os.environ.get("CAREMANAGER_DATABASE_URL")
DATABASE_NAME = os.environ.get("POSTGRES_DB")
DATABASE_USER = os.environ.get("POSTGRES_USER")
DATABASE_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DATABASE_HOST = os.environ.get("CAREMANAGER_DATABASE_HOST", "db")
API_KEY = os.environ.get("CAREMANAGER_API_KEY")

if not DATABASE_URL and not (DATABASE_NAME and DATABASE_USER and DATABASE_PASSWORD):
    raise RuntimeError("POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD must be configured")
if not API_KEY or len(API_KEY) < 24:
    raise RuntimeError("CAREMANAGER_API_KEY must contain at least 24 characters")
