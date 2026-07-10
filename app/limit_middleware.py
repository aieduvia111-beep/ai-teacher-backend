from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt, JWTError

from .database import SessionLocal
from .models import User
from .auth import SECRET_KEY, ALGORITHM
from .usage_limits import check_and_use_limit, LIMIT_MESSAGES

PROTECTED_PREFIXES = {
    "/api/v1/chat": "chat",
    "/api/v1/quiz": "quiz",
    "/api/v1/notes-pdf": "notes",
    "/api/v1/exam": "exam",
    "/api/v1/lessons": "lesson",
}

EXCLUDED_SUFFIXES = ("/health", "/ws")


def match_feature(path: str, method: str):
    if method != "POST":
        return None
    for prefix, feature in PROTECTED_PREFIXES.items():
        if path.startswith(prefix):
            if any(path.endswith(suf) for suf in EXCLUDED_SUFFIXES):
                return None
            return feature
    return None


def get_user_from_token(request: Request, db):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        return None
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


async def usage_limit_middleware(request: Request, call_next):
    feature = match_feature(request.url.path, request.method)

    if feature is None:
        return await call_next(request)

    db = SessionLocal()
    try:
        user = get_user_from_token(request, db)
        if not user:
            return await call_next(request)

        allowed, remaining = check_and_use_limit(user, db, feature)
        if not allowed:
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "limit_reached": True,
                    "title": "Limit wyczerpany",
                    "text": LIMIT_MESSAGES.get(feature, "Wykorzystałeś dzisiejszy darmowy limit."),
                    "has_latex": False, "sources": [], "videos": [], "chart": None,
                },
            )
    finally:
        db.close()

    return await call_next(request)
