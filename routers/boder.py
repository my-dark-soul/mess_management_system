from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Member, MealRecord, Item, Fine, Notice, Cleaning, MonthlyArchive
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    now = datetime.now()
    members = db.query(Member).all()
    fine_lists = db.query(Fine).order_by(Fine.fine_date.desc()).all()
    notices = db.query(Notice).order_by(Notice.created_at.desc()).limit(5).all()
    cleanings = db.query(Cleaning).order_by(Cleaning.cleaning_date.desc()).limit(5).all()

    current_monitor_member = db.query(Member).filter_by(role="manager").first()
    bajar_list = (db.query(Item)
                  .filter(Item.entry_type == "bajar",
                          Item.month == now.month, Item.year == now.year)
                  .order_by(Item.bajar_date).all())

    first_half = [i for i in bajar_list if 1 <= i.bajar_date.day <= 15]
    second_half = [i for i in bajar_list if i.bajar_date.day >= 16]

    total_meals = db.query(func.sum(MealRecord.meal_count)).scalar() or 0
    total_expense = (db.query(func.sum(Item.total_cost))
                     .filter(Item.entry_type == "bajar",
                             Item.month == now.month, Item.year == now.year)
                     .scalar() or 0)
    extra_items = (db.query(Item)
                   .filter(Item.entry_type == "extra",
                           Item.month == now.month, Item.year == now.year)
                   .all())
    extra_total = sum(i.total_cost for i in extra_items)
    total_members = db.query(Member).count()
    extra_per_head = round(extra_total / total_members, 2) if total_members > 0 else 0
    meal_rate = round(total_expense / total_meals, 2) if total_meals > 0 else 0

    return templates.TemplateResponse("boder/dashboard.html", {
        "request": request,
        "members": members,
        "fine_lists": fine_lists,
        "notices": notices,
        "cleanings": cleanings,
        "first_half": first_half,
        "second_half": second_half,
        "total_meals": total_meals,
        "total": total_expense,
        "extra_per_head": extra_per_head,
        "meal_rate": meal_rate,
        "now": now,
    })
