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
        sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        if sa_json:
            import json
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
