import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

GMAIL_USER = "aieduvia111@gmail.com"
GMAIL_PASS = "qvlc wvit hhmn pubq"
NOTIFY_EMAIL = "aieduvia111@gmail.com"

def send_error_email(service: str, error: str, details: str = ""):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = NOTIFY_EMAIL
        msg['Subject'] = f"[Eduvia] Blad w {service}"
        
        body = f"""
Eduvia Status Alert

Serwis: {service}
Blad: {error}
Czas: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
Szczegoly: {details[:300] if details else 'Brak'}

Sprawdz: https://eduvia-backend-2.onrender.com/static/status.html
        """
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
        server.quit()
        print(f"[EMAIL] Wyslano alert: {service}")
    except Exception as e:
        print(f"[EMAIL FAILED] {e}")
