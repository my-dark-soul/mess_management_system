from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import (Monitor, Member, MealRecord, Item, Fine, Notice,
                    Cleaning, SavedAmount, GasRecord, SeatRent, MonthlyArchive)
from auth import hash_password, verify_password, require_monitor
from datetime import datetime
import shutil, os, calendar

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/member_photo"
ALLOWED = {"png", "jpg", "jpeg", "gif"}


def allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED


def save_photo(file: UploadFile) -> str | None:
    if not file or not file.filename or not allowed(file.filename):
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = f"{UPLOAD_DIR}/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return f"member_photo/{file.filename}"


def guard(request: Request):
    if not request.session.get("monitor_id"):
        return RedirectResponse("/signin", status_code=302)
    return None


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    now = datetime.now()
    monitor_id = request.session["monitor_id"]
    current_monitor = db.get(Monitor, monitor_id)
    members = db.query(Member).all()
    fine_lists = db.query(Fine).order_by(Fine.fine_date.desc()).all()
    notices = db.query(Notice).order_by(Notice.created_at.desc()).all()
    cleanings = db.query(Cleaning).order_by(Cleaning.cleaning_date.desc()).all()

    total_meals = db.query(func.sum(MealRecord.meal_count)).scalar() or 0
    total_expense = db.query(func.sum(Item.total_cost)).filter_by(entry_type="bajar").scalar() or 0
    meal_rate = round(total_expense / total_meals, 2) if total_meals > 0 else 0

    member_meals = {
        m.id: db.query(func.sum(MealRecord.meal_count))
                 .filter(MealRecord.member_id == m.id).scalar() or 0
        for m in members
    }
    member_saved_meal = {
        m.id: db.query(func.sum(SavedAmount.meal_amount))
                 .filter(SavedAmount.member_id == m.id).scalar() or 0
        for m in members
    }
    member_saved_gas = {
        m.id: db.query(func.sum(SavedAmount.gas_amount))
                 .filter(SavedAmount.member_id == m.id).scalar() or 0
        for m in members
    }

    # Seat rent for current month
    seat_rents = {
        m.id: db.query(SeatRent).filter_by(
            member_id=m.id, month=now.month, year=now.year
        ).first()
        for m in members
    }

    month_name = now.strftime("%B %Y")
    archives = db.query(MonthlyArchive).order_by(
        MonthlyArchive.year.desc(), MonthlyArchive.month.desc()
    ).all()

    return templates.TemplateResponse("monitor/dashboard.html", {
        "request": request,
        "current_monitor": current_monitor,
        "members": members,
        "fine_lists": fine_lists,
        "notices": notices,
        "cleanings": cleanings,
        "total_meals": total_meals,
        "total": total_expense,
        "meal_rate": meal_rate,
        "member_meals": member_meals,
        "member_saved_meal": member_saved_meal,
        "member_saved_gas": member_saved_gas,
        "seat_rents": seat_rents,
        "month_name": month_name,
        "now": now,
        "archives": archives,
    })


# ── Add Member ───────────────────────────────────────────────────────────────

@router.get("/add-member", response_class=HTMLResponse)
async def add_member_page(request: Request):
    if r := guard(request): return r
    return templates.TemplateResponse("monitor/add_member.html", {"request": request})


@router.post("/add-member")
async def add_member(request: Request,
                     name: str = Form(...), phone: str = Form(...),
                     nid: str = Form(""), email: str = Form(""),
                     photo: UploadFile = File(None),
                     db: Session = Depends(get_db)):
    if r := guard(request): return r
    photo_path = save_photo(photo) if photo else None
    member = Member(name=name, phone=phone, nid=nid, email=email,
                    photo=photo_path, role="boder")
    db.add(member)
    db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


# ── Delete Member ────────────────────────────────────────────────────────────

@router.post("/delete-member/{member_id}")
async def delete_member(member_id: int, request: Request,
                         db: Session = Depends(get_db)):
    if r := guard(request): return r
    member = db.get(Member, member_id)
    if member:
        db.delete(member)
        db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


# ── Change Role ──────────────────────────────────────────────────────────────

@router.post("/change-role/{member_id}")
async def change_role(member_id: int, request: Request,
                      role: str = Form(...),
                      manager_password: str = Form(""),
                      db: Session = Depends(get_db)):
    if r := guard(request): return r
    member = db.get(Member, member_id)
    if not member:
        return RedirectResponse("/monitor/dashboard", status_code=302)

    # Only one manager allowed
    if role == "manager":
        existing_manager = db.query(Member).filter_by(role="manager").first()
        if existing_manager and existing_manager.id != member_id:
            return templates.TemplateResponse("monitor/dashboard.html", {
                "request": request,
                "error": f"A manager already exists: {existing_manager.name}. Remove their manager role first."
            })
        if manager_password:
            member.manager_password = hash_password(manager_password)

    # Demoting from manager: clear password
    if role == "boder" and member.role == "manager":
        member.manager_password = None

    member.role = role
    db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


# ── Seat Rent Table (save) ───────────────────────────────────────────────────

@router.post("/save-seat-rent")
async def save_seat_rent(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    data = await request.json()
    now = datetime.now()

    for entry in data:
        member_id = entry.get("member_id")
        if not member_id:
            continue
        existing = db.query(SeatRent).filter_by(
            member_id=member_id, month=now.month, year=now.year
        ).first()
        if existing:
            existing.seat_rent = entry.get("seat_rent", 0)
            existing.wifi_bill = entry.get("wifi_bill", 0)
            existing.chef_bill = entry.get("chef_bill", 0)
            existing.paid = entry.get("paid", False)
        else:
            record = SeatRent(
                member_id=member_id, month=now.month, year=now.year,
                seat_rent=entry.get("seat_rent", 0),
                wifi_bill=entry.get("wifi_bill", 0),
                chef_bill=entry.get("chef_bill", 0),
                paid=entry.get("paid", False),
            )
            db.add(record)
    db.commit()
    return JSONResponse({"success": True, "message": "Seat rent saved!"})


# ── Notices ──────────────────────────────────────────────────────────────────

@router.post("/add-notice")
async def add_notice(request: Request, title: str = Form(...),
                     description: str = Form(...), db: Session = Depends(get_db)):
    if r := guard(request): return r
    db.add(Notice(title=title, description=description))
    db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


@router.post("/delete-notice/{notice_id}")
async def delete_notice(notice_id: int, request: Request,
                         db: Session = Depends(get_db)):
    if r := guard(request): return r
    notice = db.get(Notice, notice_id)
    if notice:
        db.delete(notice)
        db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


# ── Cleaning ─────────────────────────────────────────────────────────────────

@router.post("/add-cleaning")
async def add_cleaning(request: Request, cleaning_date: str = Form(...),
                        cleaner1: str = Form(...), cleaner2: str = Form(""),
                        db: Session = Depends(get_db)):
    if r := guard(request): return r
    cleaning = Cleaning(
        cleaning_date=datetime.strptime(cleaning_date, "%Y-%m-%d"),
        cleaner1=cleaner1, cleaner2=cleaner2
    )
    db.add(cleaning)
    db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


@router.post("/delete-cleaning/{cleaning_id}")
async def delete_cleaning(cleaning_id: int, request: Request,
                           db: Session = Depends(get_db)):
    if r := guard(request): return r
    cleaning = db.get(Cleaning, cleaning_id)
    if cleaning:
        db.delete(cleaning)
        db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


# ── Fines ────────────────────────────────────────────────────────────────────

@router.post("/add-fine")
async def add_fine(request: Request, fine_date: str = Form(...),
                   criminal: str = Form(...), reason: str = Form(...),
                   fine_amount: float = Form(...), total_fine: float = Form(...),
                   db: Session = Depends(get_db)):
    if r := guard(request): return r
    fine = Fine(
        fine_date=datetime.strptime(fine_date, "%Y-%m-%d"),
        criminal=criminal, reason=reason,
        fine_amount=fine_amount, total_fine=total_fine
    )
    db.add(fine)
    db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


@router.post("/delete-fine/{fine_id}")
async def delete_fine(fine_id: int, request: Request,
                       db: Session = Depends(get_db)):
    if r := guard(request): return r
    fine = db.get(Fine, fine_id)
    if fine:
        db.delete(fine)
        db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


# ── Archive ──────────────────────────────────────────────────────────────────

@router.post("/archive-month")
async def archive_month(request: Request, db: Session = Depends(get_db)):
    """Snapshot current month and clear records"""
    if r := guard(request): return r
    now = datetime.now()
    total_meals = db.query(func.sum(MealRecord.meal_count)).scalar() or 0
    total_expense = db.query(func.sum(Item.total_cost)).filter_by(entry_type="bajar").scalar() or 0
    meal_rate = round(total_expense / total_meals, 2) if total_meals > 0 else 0
    total_members = db.query(Member).count()

    archive = MonthlyArchive(
        month=now.month, year=now.year,
        total_meals=total_meals, total_expense=total_expense,
        meal_rate=meal_rate, total_members=total_members
    )
    db.add(archive)

    # Clear monthly data
    db.query(MealRecord).delete()
    db.query(SavedAmount).delete()
    db.query(Item).filter_by(entry_type="bajar").delete()
    db.query(Item).filter_by(entry_type="extra").delete()
    db.commit()
    return RedirectResponse("/monitor/dashboard", status_code=302)


# ── Financial data save ──────────────────────────────────────────────────────

@router.post("/save-financial")
async def save_financial(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    data = await request.json()
    now = datetime.now()

    for entry in data:
        member_id = entry.get("member_id")
        if not member_id:
            continue
        saved = db.query(SavedAmount).filter_by(
            member_id=member_id, month=now.month, year=now.year
        ).first()
        if saved:
            saved.meal_amount = entry.get("meal_amount", 0)
            saved.gas_amount = entry.get("gas_amount", 0)
        else:
            db.add(SavedAmount(
                member_id=member_id,
                meal_amount=entry.get("meal_amount", 0),
                gas_amount=entry.get("gas_amount", 0),
                month=now.month, year=now.year
            ))
    db.commit()
    return JSONResponse({"success": True, "message": "Saved!"})
