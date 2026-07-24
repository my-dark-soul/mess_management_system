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
from collections import defaultdict

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
    
    members = db.query(Member).filter_by(is_active=True).all()
    fine_lists = db.query(Fine).all()
    current_monitor = db.get(Monitor, monitor_id) if monitor_id else db.query(Monitor).first()
    manager_member = db.query(Member).filter_by(role="manager").first()
    
    # 1. Filter Bajar List strictly by current month and year
    bajar_list = (
        db.query(Item)
        .filter(
            Item.entry_type == "bajar",
            extract('month', Item.bajar_date) == now.month,
            extract('year', Item.bajar_date) == now.year
        )
        .order_by(Item.bajar_date)
        .all()
    )

    first_half = [i for i in bajar_list if 1 <= i.bajar_date.day <= 15]
    second_half = [i for i in bajar_list if i.bajar_date.day >= 16]

    # 2. Calculate TOTAL MEALS strictly for the current month
    total_meals = (
        db.query(func.sum(MealRecord.meal_count))
        .filter(
            extract('month', MealRecord.meal_date) == now.month,
            extract('year', MealRecord.meal_date) == now.year
        )
        .scalar()
    ) or 0

    # 3. Calculate TOTAL REGULAR BAJAR EXPENSE (Exclude extra items)
    total_expense = sum(i.meal_cost for i in bajar_list)

    # 4. Calculate EXTRA COSTS separately
    extra_items = (
        db.query(Item)
        .filter(
            Item.entry_type == "extra",
            extract('month', Item.bajar_date) == now.month,
            extract('year', Item.bajar_date) == now.year
        )
        .all()
    )
    total_extra_cost = sum(i.total_cost for i in extra_items)
    
    # 5. Divide Extra Costs per person safely
    member_count = len(members)
    extra_per_head = total_extra_cost / member_count if member_count > 0 else 0

    # 6. Final Meal Rate Equation
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
        "extra_per_head": round(extra_per_head, 2), # Now dynamically shared with template
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

    # Safely extract month and year from the actual DateTime column
    items = (
        db.query(Item)
        .filter(
            extract('month', Item.bajar_date) == now.month,
            extract('year', Item.bajar_date) == now.year
        )
        .order_by(Item.bajar_date.desc())
        .all()
    )

    grouped_data = defaultdict(lambda: {"bajar": [], "extra": []})
    bajar_total = 0
    extra_total = 0

    for item in items:
        # Normalize date key to just the date part if it's a datetime object
        date_key = item.bajar_date.date() if hasattr(item.bajar_date, 'date') else item.bajar_date
        
        if item.entry_type == "bajar":
            grouped_data[date_key]["bajar"].append(item)
            # Make sure to fall back to 0 if meal_cost is None
            bajar_total += (item.meal_cost or 0)
        elif item.entry_type == "extra":
            grouped_data[date_key]["extra"].append(item)
            # Make sure to fall back to 0 if total_cost is None
            extra_total += (item.total_cost or 0)

    sorted_bajar_list = []
    for date_key in sorted(grouped_data.keys(), reverse=True):
        b_items = grouped_data[date_key]["bajar"]
        e_items = grouped_data[date_key]["extra"]
        
        if not b_items and e_items:
            b_items = [{"bajarkari": "-", "meal_cost": 0}]
            
        sorted_bajar_list.append({
            "date": date_key,
            "bajar": b_items,
            "extra": e_items,
            "max_rows": max(len(b_items), len(e_items))
        })

    member_count = db.query(Member).count()
    extra_per_person = extra_total / member_count if member_count > 0 else 0
    grand_total = bajar_total + extra_total

    return templates.TemplateResponse(
        "bajar.html",
        {
            "request": request,
            "bajar_list": sorted_bajar_list,
            "bajar_total": bajar_total,
            "extra_total": extra_total,
            "grand_total": grand_total,
            "extra_per_person": round(extra_per_person, 2),
            "now": now,
        }
    )


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


@router.get("/hisab", response_class=HTMLResponse)
async def hisab_page(request: Request, db: Session = Depends(get_db)):
    now = datetime.now()
    members = db.query(Member).all()
    
    # --- 1. Meal Tab Data ---
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    meal_records = db.query(MealRecord).all()
    meal_data = {m.id: {r.meal_date.day: r.meal_count for r in meal_records if r.member_id == m.id} for m in members}
    total_meals = db.query(func.sum(MealRecord.meal_count)).scalar() or 0

    # --- 2. Bajar Tab Data ---
    items = db.query(Item).filter(extract('month', Item.bajar_date) == now.month, extract('year', Item.bajar_date) == now.year).all()
    bajar_items = [i for i in items if i.entry_type == "bajar"]
    extra_items = [i for i in items if i.entry_type == "extra"]
    
    bajar_total = sum(item.meal_cost for item in bajar_items)
    extra_total = sum(item.total_cost for item in extra_items)
    
    meal_rate = bajar_total / total_meals if total_meals > 0 else 0

    # --- 3. Savings & Final Tab Calculations ---
    member_count = len(members)
    extra_per_person = extra_total / member_count if member_count > 0 else 0
    grand_total = bajar_total + extra_total

    # Mock dictionaries mimicking collections mapping (Replace with your actual DB dynamic query hooks)
    member_meals = {m.id: sum(meal_data[m.id].values()) for m in members}
    member_saved_meal = {m.id: 0 for m in members}  # Replace with actual DB query if available
    member_saved_gas = {m.id: 0 for m in members}   # Replace with actual DB query if available

    return templates.TemplateResponse("hisab.html", {
        "request": request,
        "now": now,
        "members": members,
        "meal_data": meal_data,
        "days_in_month": days_in_month,
        "bajar_items": bajar_items,
        "extra_items": extra_items,
        "bajar_total": bajar_total,
        "extra_total": extra_total,
        "grand_total": grand_total,
        "meal_rate": round(meal_rate, 2),
        "extra_per_person": round(extra_per_person, 2),
        "member_meals": member_meals,
        "member_saved_meal": member_saved_meal,
        "member_saved_gas": member_saved_gas
    })