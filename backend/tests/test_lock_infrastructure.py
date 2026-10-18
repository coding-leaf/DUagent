import hashlib

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.locks import LockAcquisitionTimeout, profile_lock


# `profile_lock` derives the MySQL GET_LOCK key from a truncated MD5 of
# "profile_<user_id>_<course_id>". Compute it here instead of hardcoding the
# digest so the assertion stays in sync with the implementation.
EXPECTED_LOCK_KEY = hashlib.md5(b"profile_user123_course456").hexdigest()[:32]

@pytest.mark.asyncio
async def test_profile_lock_acquisition_success():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    db.execute.return_value = mock_result
    db.bind.dialect.name = "mysql"
    
    async with profile_lock(db, "user123", "course456"):
        pass

    assert db.execute.call_count == 2
    # Verify GET_LOCK call
    first_args = db.execute.call_args_list[0]
    assert "GET_LOCK" in str(first_args[0][0])
    assert first_args[1]["params"] == {"key": EXPECTED_LOCK_KEY}
    # Verify RELEASE_LOCK call
    second_args = db.execute.call_args_list[1]
    assert "RELEASE_LOCK" in str(second_args[0][0])
    assert second_args[1]["params"] == {"key": EXPECTED_LOCK_KEY}

@pytest.mark.asyncio
async def test_profile_lock_acquisition_timeout():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    db.execute.return_value = mock_result
    db.bind.dialect.name = "mysql"

    with pytest.raises(LockAcquisitionTimeout):
        async with profile_lock(db, "user123", "course456"):
            pass
