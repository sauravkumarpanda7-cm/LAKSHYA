import os
import smtplib
from email.mime.text import MIMEText


def send_otp(to_email, code):
    """Send a 6-digit OTP. If SMTP is not configured, print to console."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    pw   = os.environ.get("SMTP_PASS")

    if not (host and user and pw):
        # Dev fallback — printed in your Flask terminal
        print("\n" + "=" * 60)
        print(f"  🔐 OTP for {to_email}:  {code}")
        print("=" * 60 + "\n")
        return True

    msg = MIMEText(
        f"Your LAKSHYA verification code is: {code}\n\n"
        f"It expires in 10 minutes.\n\n"
        f"If you didn't request this, ignore this email."
    )
    msg["Subject"] = "LAKSHYA — Verify your email"
    msg["From"] = user
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        print("Email send failed:", e)
        print("\n" + "=" * 60)
        print(f"  🔐 FALLBACK OTP for {to_email}:  {code}")
        print("=" * 60 + "\n")
        return False