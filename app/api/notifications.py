from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

def get_firestore():
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

class FCMTokenRequest(BaseModel):
    uid: str
    fcm_token: str

@router.post("/save-token")
def save_fcm_token(req: FCMTokenRequest):
    """Zapisuje token urzadzenia (FCM) w Firestore, do wysylania powiadomien push"""
    db = get_firestore()
    user_ref = db.collection('users').document(req.uid)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="Uzytkownik nie znaleziony")
    user_ref.update({'fcmToken': req.fcm_token})
    return {"success": True}
