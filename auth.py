from passlib.context import CryptContext
from fastapi import Request
from fastapi.responses import RedirectResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_monitor_session(request: Request):
    return request.session.get("monitor_id")


def get_manager_session(request: Request):
    return request.session.get("manager_id")


def get_boder_session(request: Request):
    return request.session.get("boder_id")


def require_monitor(request: Request):
    if not request.session.get("monitor_id"):
        return RedirectResponse("/signin", status_code=302)
    return None


def require_manager(request: Request):
    if not request.session.get("manager_id") and not request.session.get("monitor_id"):
        return RedirectResponse("/manager/signin", status_code=302)
    return None
