import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

GMAIL_USER = "aieduvia111@gmail.com"
GMAIL_PASS = "qvlc wvit hhmn pubq"
NOTIFY_EMAIL = "aieduvia111@gmail.com"


def send_user_email(to_email: str, subject: str, body_text: str, body_html: str = None) -> bool:
    """Wysyla e-mail DO UZYTKOWNIKA (w odroznieniu od send_error_email, ktory
    zawsze leci na NOTIFY_EMAIL czyli do nas). Uzywane jako kanal zapasowy
    tam, gdzie push (FCM) zawodzi strukturalnie - patrz komentarz przy
    _run_abandoned_checkout_reminder w app/api/notifications.py: 27.09.2026
    real prod, WSZYSTKIE 6/6 checkoutow porzuconych tego dnia mialo
    "Brak tokenu FCM" (token to opt-in banner ktory wyskakuje raz w zyciu
    urzadzenia i nic nie robi dla iOS WKWebView, gdzie Web Push w ogole nie
    dziala) - wiec push mial 0% dostarczalnosci, mail idzie zawsze."""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html'))

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL] Wyslano do uzytkownika: {to_email} ({subject})")
        return True
    except Exception as e:
        print(f"[EMAIL USER FAILED] {to_email}: {e}")
        return False

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
