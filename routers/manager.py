from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from database import get_db
from models import Member, MealRecord, Item, SavedAmount, GasRecord
from datetime import datetime
import calendar

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def guard(request: Request):
    if not request.session.get("manager_id") and not request.session.get("monitor_id"):
        return RedirectResponse("/manager/signin", status_code=302)
    return None


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    now = datetime.now()
    
    # 1. Base active operations entirely on active members list
    members = db.query(Member).filter_by(is_active=True).all()
    days_in_month = calendar.monthrange(now.year, now.month)[1]

    # 2. Total Meals calculated strictly for the current Month and Year
    total_meals = (
        db.query(func.sum(MealRecord.meal_count))
        .filter(
            extract('month', MealRecord.meal_date) == now.month,
            extract('year', MealRecord.meal_date) == now.year
        )
        .scalar()
    ) or 0

    # 3. Total Expense calculated strictly for current month items
    total_expense = (
        db.query(func.sum(Item.total_cost))
        .filter(
            Item.entry_type == "bajar",
            Item.month == now.month, 
            Item.year == now.year
        )
        .scalar()
    ) or 0

    # 4. Strict matching single assignment Meal Rate Equation
    meal_rate = round(total_expense / total_meals, 2) if total_meals > 0 else 0
                     
    extra_items = (db.query(Item)
                   .filter(Item.entry_type == "extra",
                           Item.month == now.month, Item.year == now.year)
                   .all())
                   
    extra_total = sum(i.total_cost for i in extra_items)
    total_members = len(members) 
    
    extra_per_head = round(extra_total / total_members, 2) if total_members > 0 else 0

    # Tomorrow's meal verification setup
    from datetime import timedelta
    tomorrow_dt = datetime.now() + timedelta(days=1)
    tomorrow_start = tomorrow_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    tomorrow_meal = {}
    for member in members:
        record = db.query(MealRecord).filter_by(
            member_id=member.id,
            meal_date=tomorrow_start
        ).first()
        tomorrow_meal[member.id] = record.meal_count if record else 0.0

    # 5. Scoped Monthly Bulk Queries to match /home data matrix exactly
    meal_totals = db.query(MealRecord.member_id, func.sum(MealRecord.meal_count))\
                    .filter(extract('month', MealRecord.meal_date) == now.month,
                            extract('year', MealRecord.meal_date) == now.year)\
                    .group_by(MealRecord.member_id).all()
    member_meals = {m_id: count or 0 for m_id, count in meal_totals}

    saved_meals = db.query(SavedAmount.member_id, func.sum(SavedAmount.meal_amount))\
                    .filter(SavedAmount.month == now.month, SavedAmount.year == now.year)\
                    .group_by(SavedAmount.member_id).all()
    member_saved_meal = {m_id: amt or 0 for m_id, amt in saved_meals}

    saved_gas = db.query(SavedAmount.member_id, func.sum(SavedAmount.gas_amount))\
                   .filter(SavedAmount.month == now.month, SavedAmount.year == now.year)\
                   .group_by(SavedAmount.member_id).all()
    member_saved_gas = {m_id: amt or 0 for m_id, amt in saved_gas}

    # Initialize dictionary structure for new tracking cycles
    for m in members:
        if m.id not in member_meals: member_meals[m.id] = 0
        if m.id not in member_saved_meal: member_saved_meal[m.id] = 0
        if m.id not in member_saved_gas: member_saved_gas[m.id] = 0

    manager_id = request.session.get("manager_id")
    current_manager = db.get(Member, manager_id) if manager_id else None

    return templates.TemplateResponse("manager/dashboard.html", {
        "request": request,
        "members": members,
        "days_in_month": days_in_month,
        "total_meals": total_meals,
        "total_expense": total_expense,
        "extra_items": extra_items,
        "extra_total": extra_total,
        "extra_per_head": extra_per_head,
        "meal_rate": meal_rate,
        "member_meals": member_meals,
        "member_saved_meal": member_saved_meal,
        "member_saved_gas": member_saved_gas,
        "now": now,
        "current_manager": current_manager,
        "tomorrow_meal": tomorrow_meal,
    })


# ── Save Meal Data ───────────────────────────────────────────────────────────

@router.post("/save-meals")
async def save_meals(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    data = await request.json()
    now = datetime.now()

    if not data or not isinstance(data, list):
        return JSONResponse({"success": False, "message": "Invalid data"}, status_code=400)

    for entry in data:
        member_id = entry.get("member_id")
        meal_counts = entry.get("meal_counts", [])
        if not member_id:
            continue
        for i, count in enumerate(meal_counts):
            meal_date = datetime(now.year, now.month, i + 1)
            existing = db.query(MealRecord).filter_by(
                member_id=member_id, meal_date=meal_date
            ).first()
            if existing:
                existing.meal_count = float(count)
            else:
                db.add(MealRecord(member_id=member_id,
                                  meal_date=meal_date, meal_count=float(count)))
    db.query()
    db.commit()
    return JSONResponse({"success": True, "message": "Meal data saved!"})


# ── Save Daily Meal ──────────────────────────────────────────────────────────

@router.post("/save-daily-meal")
async def save_daily_meal(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    data = await request.json()

    for entry in data:
        member_id = entry.get("member_id")
        date_str = entry.get("date")
        meal_count = float(entry.get("meal_count", 0))

        if not member_id or not date_str:
            continue

        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        meal_date = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)

        existing = db.query(MealRecord).filter_by(
            member_id=member_id,
            meal_date=meal_date
        ).first()

        if existing:
            existing.meal_count = meal_count
        else:
            db.add(MealRecord(
                member_id=member_id,
                meal_date=meal_date,
                meal_count=meal_count
            ))

    db.commit()
    return JSONResponse({"success": True, "message": "Meal data saved successfully!"})


# ── Toggle Single Meal Cell ──────────────────────────────────────────────────

@router.post("/toggle-meal")
async def toggle_meal(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    data = await request.json()
    member_id = data.get("member_id")
    day = data.get("day")
    value = float(data.get("value", 0))
    now = datetime.now()
    meal_date = datetime(now.year, now.month, day)

    existing = db.query(MealRecord).filter_by(
        member_id=member_id, meal_date=meal_date
    ).first()
    if existing:
        existing.meal_count = value
    else:
        db.add(MealRecord(member_id=member_id, meal_date=meal_date, meal_count=value))
    db.commit()
    return JSONResponse({"success": True})


# ── Add Extra Cost ───────────────────────────────────────────────────────────

@router.post("/add-extra-cost")
async def add_extra_cost(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    now = datetime.now()
    items = data.get("items", [])

    for item in items:
        name = item.get("name", "").strip()
        try:
            cost = float(item.get("cost", 0))
        except (ValueError, TypeError):
            continue

        if not name or cost <= 0:
            continue
            
        db.add(Item(
            bajar_date=now.date(),
            bajarkari="-",          
            meal_cost=0,
            extra_name=name,           
            total_cost=cost,
            entry_type="extra",
            month=now.month,
            year=now.year,
        ))
        
    db.commit()
    return JSONResponse({"success": True, "message": "Extra costs added!"})


# ── Save Financial Collection ────────────────────────────────────────────────

@router.post("/save-financial")
async def save_financial(request: Request, db: Session = Depends(get_db)):
    if r := guard(request): return r
    data = await request.json()
    now = datetime.now()

    for entry in data:
        member_id = entry.get("member_id")
        if not member_id:
            continue
            
        meal_amount = float(entry.get("meal_amount", 0))
        gas_amount = float(entry.get("gas_amount", 0))

        saved = db.query(SavedAmount).filter_by(
            member_id=member_id, month=now.month, year=now.year
        ).first()
        
        if saved:
            saved.meal_amount = meal_amount
            saved.gas_amount = gas_amount
        else:
            db.add(SavedAmount(
                member_id=member_id,
                meal_amount=meal_amount,
                gas_amount=gas_amount,
                month=now.month, 
                year=now.year
            ))
            
    db.commit()
    return JSONResponse({"success": True, "message": "Financial data successfully saved!"})


# ── Add Bajar Item ───────────────────────────────────────────────────────────

@router.post("/add-bajar")
async def add_bajar(request: Request,
                    bajar_date: str = Form(...),
                    bajarkari: str = Form(...),
                    meal_cost: float = Form(...),
                    extra: str = Form(""),
                    totalCost: float = Form(...),
                    db: Session = Depends(get_db)):
    if r := guard(request): return r
    
    parsed_bajar_date = datetime.strptime(bajar_date, "%Y-%m-%d")
    
    item = Item(
        bajar_date=parsed_bajar_date,
        bajarkari=bajarkari,
        meal_cost=meal_cost,
        extra=float(extra) if extra else None,
        total_cost=totalCost,
        entry_type="bajar",
        # Use parsed date parameters so historical entries map to their own month block!
        month=parsed_bajar_date.month,
        year=parsed_bajar_date.year,
    )
    db.add(item)
    db.commit()
    return RedirectResponse("/manager/dashboard", status_code=302)