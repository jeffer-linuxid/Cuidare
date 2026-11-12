from sqlalchemy import URL, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_HOST, DATABASE_NAME, DATABASE_PASSWORD, DATABASE_URL, DATABASE_USER

if DATABASE_URL:
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
else:
    database_url = URL.create(
        "postgresql+psycopg",
        username=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=5432,
        database=DATABASE_NAME,
    )
    engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
