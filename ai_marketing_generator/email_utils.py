import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_campaign_email(subject, body_html, recipient_list):
    """
    Sends the approved campaign email to a list of recipients using Gmail SMTP.
    Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env
    (use a Gmail App Password, not your normal password).
    Returns (success: bool, message: str)
    """
    sender_email = os.environ.get("GMAIL_ADDRESS")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender_email or not sender_password:
        return False, "Gmail credentials not configured in .env - email not sent (demo mode)."

    if not recipient_list:
        return False, "No customers found to send email to."

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)

        for recipient in recipient_list:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender_email
            msg["To"] = recipient
            msg.attach(MIMEText(body_html, "html"))
            server.sendmail(sender_email, recipient, msg.as_string())

        server.quit()
        return True, f"Email sent successfully to {len(recipient_list)} customer(s)."

    except Exception as e:
        return False, f"Failed to send email: {e}"


def send_otp_email(recipient_email, otp_code, purpose="account"):
    """
    Sends a one-time password to a single recipient (owner/manager account
    verification, or customer email verification). Reuses the same Gmail
    SMTP setup as send_campaign_email.
    Returns (success: bool, message: str)
    """
    sender_email = os.environ.get("GMAIL_ADDRESS")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender_email or not sender_password:
        return False, "Gmail credentials not configured in .env - OTP not sent (demo mode)."

    subject = "Your verification code"
    body_html = f"""
    <p>Hi,</p>
    <p>Your verification code for {purpose} is:</p>
    <h2>{otp_code}</h2>
    <p>This code is valid for 10 minutes. If you did not request this, you can ignore this email.</p>
    """

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.attach(MIMEText(body_html, "html"))
        server.sendmail(sender_email, recipient_email, msg.as_string())

        server.quit()
        return True, f"OTP sent to {recipient_email}."

    except Exception as e:
        return False, f"Failed to send OTP: {e}"
