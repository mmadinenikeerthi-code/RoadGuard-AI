# ==========================================================
# backend/database.py
# ROADGUARD AI DATABASE
# ==========================================================

from sqlalchemy import create_engine

from sqlalchemy.orm import (
    sessionmaker,
    declarative_base
)

from backend.config import DATABASE_URL


# ==========================================================
# DATABASE ENGINE
# ==========================================================

engine = create_engine(

    DATABASE_URL,

    connect_args={
        "check_same_thread": False
    }

)


# ==========================================================
# DATABASE SESSION
# ==========================================================

SessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=engine

)


# ==========================================================
# BASE MODEL
# ==========================================================

Base = declarative_base()


# ==========================================================
# DATABASE DEPENDENCY
# ==========================================================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()