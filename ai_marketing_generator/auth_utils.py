import random
from datetime import datetime, timedelta

OTP_VALID_MINUTES = 10


def generate_otp():
    """Returns a random 6-digit OTP code as a string, e.g. '482913'."""
    return str(random.randint(100000, 999999))


def get_otp_expiry():
    """Returns the datetime at which a freshly generated OTP should stop being valid."""
    return datetime.utcnow() + timedelta(minutes=OTP_VALID_MINUTES)


def is_otp_valid(stored_code, stored_expiry, entered_code):
    """
    Checks an OTP entered by the user against what's stored on the User/Customer record.
    Returns (is_valid: bool, error_message: str or None)
    """
    if not stored_code or not stored_expiry:
        return False, "No OTP was requested. Please register or add the customer again."

    if datetime.utcnow() > stored_expiry:
        return False, "This OTP has expired. Please request a new one."

    if entered_code.strip() != stored_code:
        return False, "Incorrect OTP. Please check and try again."

    return True, None
