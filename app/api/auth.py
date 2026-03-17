"""🔐 AUTH API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime
from ..database import get_db
from ..models import User
from ..auth import get_password_hash, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email już istnieje")
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username zajęty")
    
    user = User(email=req.email, username=req.username, hashed_password=get_password_hash(req.password), is_premium=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"✅ User zarejestrowany: {user.email}")
    return {"success": True, "user": {"id": user.id, "email": user.email, "username": user.username}}

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Nieprawidłowe dane")
    
    user.last_login = datetime.utcnow()
    db.commit()
    
    token = create_access_token({"sub": user.email})
    print(f"✅ User zalogowany: {user.email}")
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "is_premium": user.is_premium}}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "username": current_user.username, "is_premium": current_user.is_premium}