from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class Monitor(Base):
    __tablename__ = "monitors"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    password = Column(String(200), nullable=False)
    photo = Column(String(200), nullable=True)
    mess_location = Column(String(100), nullable=False)


class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    nid = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    photo = Column(String(100), nullable=True)
    # roles: 'boder', 'manager'
    role = Column(String(20), nullable=False, default="boder")
    # manager login password (set when role changed to manager)
    manager_password = Column(String(200), nullable=True)

    meal_records = relationship("MealRecord", back_populates="member", cascade="all, delete-orphan")
    saved_amounts = relationship("SavedAmount", back_populates="member", cascade="all, delete-orphan")
    gas_records = relationship("GasRecord", back_populates="member", cascade="all, delete-orphan")
    seat_rents = relationship("SeatRent", back_populates="member", cascade="all, delete-orphan")


class MealRecord(Base):
    __tablename__ = "meal_records"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    meal_date = Column(DateTime, nullable=False)
    meal_count = Column(Float, nullable=False, default=0)
    member = relationship("Member", back_populates="meal_records")


class GasRecord(Base):
    __tablename__ = "gas_records"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    gas_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    gas_amount = Column(Float, nullable=False, default=0)
    member = relationship("Member", back_populates="gas_records")


class SavedAmount(Base):
    __tablename__ = "saved_amounts"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    meal_amount = Column(Float, default=0)
    gas_amount = Column(Float, default=0)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    member = relationship("Member", back_populates="saved_amounts")


class Item(Base):
    """Bajar/shopping list entries — also used for extra costs added by manager"""
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    bajar_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    bajarkari = Column(String(100), nullable=False)
    meal_cost = Column(Float, nullable=False, default=0)
    extra = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=False)
    # 'bajar' = normal shopping, 'extra' = manager extra cost entry
    entry_type = Column(String(20), nullable=False, default="bajar")
    month = Column(Integer, nullable=False, default=datetime.utcnow().month)
    year = Column(Integer, nullable=False, default=datetime.utcnow().year)


class Notice(Base):
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Cleaning(Base):
    __tablename__ = "cleanings"
    id = Column(Integer, primary_key=True)
    cleaning_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    cleaner1 = Column(String(100), nullable=False)
    cleaner2 = Column(String(100), nullable=True)


class Fine(Base):
    __tablename__ = "fines"
    id = Column(Integer, primary_key=True)
    fine_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    criminal = Column(String(100), nullable=False)
    reason = Column(String(200), nullable=False)
    fine_amount = Column(Float, nullable=False)
    total_fine = Column(Float, nullable=False)


class SeatRent(Base):
    """Monthly seat rent, wifi, chef bill per member — collected by monitor"""
    __tablename__ = "seat_rents"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    seat_rent = Column(Float, default=0)
    wifi_bill = Column(Float, default=0)
    chef_bill = Column(Float, default=0)
    paid = Column(Boolean, default=False)
    member = relationship("Member", back_populates="seat_rents")


class MonthlyArchive(Base):
    """Snapshot of each month's summary — created when month resets"""
    __tablename__ = "monthly_archives"
    id = Column(Integer, primary_key=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    total_meals = Column(Float, default=0)
    total_expense = Column(Float, default=0)
    meal_rate = Column(Float, default=0)
    total_members = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
