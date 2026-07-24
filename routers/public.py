from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from database import get_db
from models import Monitor, Member, MealRecord, Item, Fine, Notice, Cleaning
from auth import hash_password, verify_password
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


# ── Home ────────────────────────────────────────────────────────────────────

@router.get("/home", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    monitor_id = request.session.get("monitor_id")
    now = datetime.now()
    members = db.query(Member).all()
    fine_lists = db.query(Fine).all()
    current_monitor = db.get(Monitor, monitor_id) if monitor_id else db.query(Monitor).first()
    manager_member = db.query(Member).filter_by(role="manager").first()
    bajar_list = db.query(Item).filter_by(entry_type="bajar").order_by(Item.bajar_date).all()

    first_half = [i for i in bajar_list if 1 <= i.bajar_date.day <= 15]
    second_half = [i for i in bajar_list if i.bajar_date.day >= 16]

    total_meals = db.query(func.sum(MealRecord.meal_count)).scalar() or 0
    total_expense = db.query(func.sum(Item.total_cost)).scalar() or 0
    meal_rate = total_expense / total_meals if total_meals > 0 else 0

    return templates.TemplateResponse("home.html", {
        "request": request,
        "members": members,
        "current_monitor": current_monitor,
        "manager_member": manager_member,
        "first_half": first_half,
        "second_half": second_half,
        "now": now,
        "fine_lists": fine_lists,
        "total_meals": total_meals,
        "total": total_expense,
        "meal_rate": round(meal_rate, 2),
        "extra_per_head": 0,
    })


# ── Signin / Signup (Monitor) ────────────────────────────────────────────────

@router.get("/signin", response_class=HTMLResponse)
async def signin_page(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})


@router.post("/signin")
async def signin(request: Request, phone: str = Form(...), password: str = Form(...),
                 db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter_by(phone=phone).first()
    if monitor and verify_password(password, monitor.password):
        request.session["monitor_id"] = monitor.id
        request.session["monitor_name"] = monitor.name
        return RedirectResponse("/monitor/dashboard", status_code=302)
    return templates.TemplateResponse("signin.html", {
        "request": request, "error": "Invalid phone or password"
    })


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@router.post("/signup")
async def signup(request: Request,
                 name: str = Form(...), email: str = Form(...),
                 phone: str = Form(...), password: str = Form(...),
                 confirm_password: str = Form(...), mess_location: str = Form(...),
                 photo: UploadFile = File(None), db: Session = Depends(get_db)):
    if password != confirm_password:
        return templates.TemplateResponse("signup.html", {
            "request": request, "error": "Passwords do not match"
        })
    if db.query(Monitor).filter_by(email=email).first():
        return templates.TemplateResponse("signup.html", {
            "request": request, "error": "Email already registered"
        })
    photo_path = save_photo(photo) if photo else None
    monitor = Monitor(name=name, email=email, phone=phone,
                      password=hash_password(password),
                      photo=photo_path, mess_location=mess_location)
    db.add(monitor)
    db.commit()
    return RedirectResponse("/signin", status_code=302)


# ── Manager Signin ───────────────────────────────────────────────────────────

@router.get("/manager/signin", response_class=HTMLResponse)
async def manager_signin_page(request: Request):
    return templates.TemplateResponse("manager_signin.html", {"request": request})


@router.post("/manager/signin")
async def manager_signin(request: Request, phone: str = Form(...),
                          password: str = Form(...), db: Session = Depends(get_db)):
    member = db.query(Member).filter_by(phone=phone, role="manager").first()
    if member and member.manager_password and verify_password(password, member.manager_password):
        request.session["manager_id"] = member.id
        request.session["manager_name"] = member.name
        return RedirectResponse("/manager/dashboard", status_code=302)
    return templates.TemplateResponse("manager_signin.html", {
        "request": request, "error": "Invalid credentials or not a manager"
    })


# ── Signout ──────────────────────────────────────────────────────────────────

@router.get("/signout")
async def signout(request: Request):
    request.session.clear()
    return RedirectResponse("/signin", status_code=302)


# ── Members public page ──────────────────────────────────────────────────────

@router.get("/members", response_class=HTMLResponse)
async def members_page(request: Request, db: Session = Depends(get_db)):
    members = db.query(Member).all()
    return templates.TemplateResponse("members.html", {"request": request, "members": members})


# ── Notice public ────────────────────────────────────────────────────────────

@router.get("/notices", response_class=HTMLResponse)
async def notices_page(request: Request, db: Session = Depends(get_db)):
    notices = db.query(Notice).order_by(Notice.created_at.desc()).all()
    return templates.TemplateResponse("notice.html", {"request": request, "notices": notices})


# ── Cleaning public ──────────────────────────────────────────────────────────

@router.get("/cleaning", response_class=HTMLResponse)
async def cleaning_page(request: Request, db: Session = Depends(get_db)):
    cleanings = db.query(Cleaning).order_by(Cleaning.cleaning_date.desc()).all()
    return templates.TemplateResponse("cleaning.html", {"request": request, "cleanings": cleanings})


# ── Bajar public ─────────────────────────────────────────────────────────────

@router.get("/bajar", response_class=HTMLResponse)
async def bajar_page(request: Request, db: Session = Depends(get_db)):
    now = datetime.now()
    bajar_list = (db.query(Item)
                  .filter(Item.month == now.month, Item.year == now.year)
                  .order_by(Item.bajar_date.desc()).all())
    extra_items = (db.query(Item)
                   .filter(Item.entry_type == "extra",
                           Item.month == now.month, Item.year == now.year)
                   .all())
    total_members = db.query(Member).count()
    extra_total = sum(i.total_cost for i in extra_items)
    extra_per_head = round(extra_total / total_members, 2) if total_members > 0 else 0
    return templates.TemplateResponse("bajar.html", {
        "request": request,
        "bajar_list": [i for i in bajar_list if i.entry_type == "bajar"],
        "extra_items": extra_items,
        "extra_total": extra_total,
        "extra_per_head": extra_per_head,
        "now": now,
    })


# ── Meal table (public view) ─────────────────────────────────────────────────

@router.get("/meal", response_class=HTMLResponse)
async def meal_page(request: Request, db: Session = Depends(get_db)):
    now = datetime.now()
    members = db.query(Member).all()
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    meal_data = {}
    for member in members:
        records = db.query(MealRecord).filter_by(member_id=member.id).all()
        meal_data[member.id] = {r.meal_date.day: r.meal_count for r in records}
    return templates.TemplateResponse("meal_rent.html", {
        "request": request,
        "members": members,
        "meal_data": meal_data,
        "days_in_month": days_in_month,
        "readonly": True,
    })
