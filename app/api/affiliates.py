from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os

router = APIRouter(prefix="/api/v1/affiliates", tags=["affiliates"])

def get_db():
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        import json, base64
        sa_b64 = os.environ.get('FIREBASE_KEY_B64')
        sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        if sa_b64:
            cred = credentials.Certificate(json.loads(base64.b64decode(sa_b64).decode('utf-8')))
        elif sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
        else:
            cred = credentials.Certificate('app/eduvia-c69bc-firebase-adminsdk-fbsvc-be39724e72.json')
        firebase_admin.initialize_app(cred)
    return firestore.client()

class AffiliateCreate(BaseModel):
    code: str
    name: str
    email: str
    commission: float = 0.30

class AffiliateCheck(BaseModel):
    code: str

class AffiliateSale(BaseModel):
    code: str
    amount: float = 29.0
    buyer_uid: Optional[str] = None

@router.post("/create")
async def create_affiliate(req: AffiliateCreate):
    try:
        db = get_db()
        code = req.code.upper().strip()
        ref = db.collection('affiliates').document(code)
        if ref.get().exists:
            return {"success": False, "error": "Kod juz istnieje"}
        ref.set({
            "code": code,
            "name": req.name,
            "email": req.email,
            "commission": req.commission,
            "sales": 0,
            "earnings": 0.0,
            "created_at": datetime.utcnow().isoformat(),
            "active": True
        })
        return {"success": True, "code": code}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/check")
async def check_affiliate(req: AffiliateCheck):
    try:
        db = get_db()
        code = req.code.upper().strip()
        doc = db.collection('affiliates').document(code).get()
        if doc.exists and doc.to_dict().get('active'):
            return {"success": True, "valid": True, "name": doc.to_dict()["name"]}
        return {"success": True, "valid": False}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/sale")
async def register_sale(req: AffiliateSale):
    try:
        db = get_db()
        code = req.code.upper().strip()
        ref = db.collection('affiliates').document(code)
        doc = ref.get()
        if not doc.exists:
            return {"success": False, "error": "Kod nie istnieje"}
        data = doc.to_dict()
        commission = req.amount * data["commission"]
        ref.update({
            "sales": data["sales"] + 1,
            "earnings": round(data["earnings"] + commission, 2)
        })
        # Zapisz sprzedaz
        db.collection('affiliate_sales').add({
            "code": code,
            "amount": req.amount,
            "commission": commission,
            "buyer_uid": req.buyer_uid,
            "timestamp": datetime.utcnow().isoformat()
        })
        return {"success": True, "commission": round(commission, 2)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/stats/{code}")
async def get_stats(code: str):
    try:
        db = get_db()
        code = code.upper().strip()
        doc = db.collection('affiliates').document(code).get()
        if not doc.exists:
            return {"success": False, "error": "Kod nie istnieje"}
        return {"success": True, "stats": doc.to_dict()}
    except Exception as e:
        return {"success": False, "error": str(e)}

class AffiliateGenerate(BaseModel):
    user_id: str
    name: str
    email: str
    admin_key: str = ""

@router.post("/generate")
async def generate_affiliate(req: AffiliateGenerate):
    import os
    ADMIN_KEY = os.environ.get("AFFILIATE_ADMIN_KEY", "")
    if not ADMIN_KEY or req.admin_key != ADMIN_KEY:
        return {"success": False, "error": "Brak uprawnien - ten endpoint wymaga klucza administratora"}
    try:
        db = get_db()
        import random, string
        # Sprawdz czy juz ma kod
        existing = db.collection('affiliates').where('user_id', '==', req.user_id).limit(1).get()
        if existing:
            for doc in existing:
                return {"success": True, "code": doc.id, "stats": doc.to_dict()}
        # Generuj unikalny kod
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        code = f"EDU{suffix}"
        db.collection('affiliates').document(code).set({
            "code": code,
            "user_id": req.user_id,
            "name": req.name,
            "email": req.email,
            "commission": 0.30,
            "sales": 0,
            "earnings": 0.0,
            "created_at": datetime.utcnow().isoformat(),
            "active": True
        })
        return {"success": True, "code": code}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/by-user/{user_id}")
async def get_by_user(user_id: str):
    try:
        db = get_db()
        docs = db.collection('affiliates').where('user_id', '==', user_id).limit(1).get()
        for doc in docs:
            return {"success": True, "code": doc.id, "stats": doc.to_dict()}
        return {"success": False}
    except Exception as e:
        return {"success": False, "error": str(e)}
