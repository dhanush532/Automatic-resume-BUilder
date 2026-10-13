import re

import phonenumbers
from pydantic import EmailStr

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")


def normalize_email(value: str | EmailStr) -> str:
    return str(value).strip().lower()


def normalize_username(value: str) -> str:
    normalized = value.strip().casefold()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("Username must be 3–30 characters using letters, numbers, periods, underscores, or hyphens.")
    return normalized


def normalize_phone(value: str | None, region: str | None = None) -> str | None:
    if not value or not value.strip():
        return None
    compact = re.sub(r"[\s().-]", "", value.strip())
    if not compact.startswith("+") and not region:
        raise ValueError("Select your phone country or include a country code, such as +91.")
    try:
        number = phonenumbers.parse(compact, region)
    except phonenumbers.NumberParseException as error:
        raise ValueError("Enter a valid phone number for the selected country.") from error
    if not phonenumbers.is_possible_number(number):
        raise ValueError("Enter a valid phone number for the selected country.")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
