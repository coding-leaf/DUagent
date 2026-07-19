from pathlib import Path
import re

from app.core.security import hash_password, verify_password


def test_password_hash_round_trip_supports_current_bcrypt_backend():
    hashed = hash_password("Admin123456")

    assert verify_password("Admin123456", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_schema_seed_admin_password_matches_documented_password():
    schema = Path(__file__).resolve().parents[1] / "schema.sql"
    content = schema.read_text(encoding="utf-8")
    match = re.search(
        r"admin@admin\.com',\s*'(?P<hash>\$2[aby]\$[^']+)'",
        content,
        re.MULTILINE,
    )

    assert match is not None
    assert verify_password("Admin123456", match.group("hash")) is True
