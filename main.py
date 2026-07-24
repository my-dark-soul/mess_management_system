from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from database import init_db
import os

# Import all routers
from routers import monitor, manager, boder, public

app = FastAPI(title="Mess Management System")

# Session middleware
app.add_middleware(SessionMiddleware, secret_key="mess_secret_key_2024_change_this")

# Static files
os.makedirs("static", exist_ok=True)
os.makedirs("static/member_photo", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(public.router)
app.include_router(monitor.router, prefix="/monitor")
app.include_router(manager.router, prefix="/manager")
app.include_router(boder.router, prefix="/boder")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
async def root():
    return RedirectResponse("/home")
