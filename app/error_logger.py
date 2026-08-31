import os
from datetime import datetime
from .email_notifier import send_error_email

def log_error(service: str, error: str, details: str = ""):
    try:
        import firebase_admin
        from firebase_admin import firestore
        if not firebase_admin._apps:
            import json, base64
            from firebase_admin import credentials
            sa_b64 = os.environ.get('FIREBASE_KEY_B64')
            sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
            sa_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
            if sa_b64:
                cred = credentials.Certificate(json.loads(base64.b64decode(sa_b64).decode('utf-8')))
            elif sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
            elif sa_path:
                cred = credentials.Certificate(sa_path)
            else:
                return
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        db.collection('errors').add({
            'service': service,
            'error': error,
            'details': details[:500],
            'timestamp': datetime.utcnow().isoformat(),
            'resolved': False
        })
        print(f"[ERROR LOG] {service}: {error}")
        send_error_email(service, error, details)
    except Exception as e:
        print(f"[ERROR LOG FAILED] {e}")
