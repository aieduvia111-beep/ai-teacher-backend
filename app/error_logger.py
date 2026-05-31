import os
from datetime import datetime
from .email_notifier import send_error_email

def log_error(service: str, error: str, details: str = ""):
    try:
        import firebase_admin
        from firebase_admin import firestore
        if not firebase_admin._apps:
            from firebase_admin import credentials
            cred = credentials.Certificate(os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH', 'app/eduvia-c69bc-firebase-adminsdk-fbsvc-be39724e72.json'))
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
