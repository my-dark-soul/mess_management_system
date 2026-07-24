from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./mess_management.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import (Monitor, Member, MealRecord, GasRecord, SavedAmount,
                        Item, Notice, Cleaning, Fine, SeatRent, MonthlyArchive)
    Base.metadata.create_all(bind=engine)
