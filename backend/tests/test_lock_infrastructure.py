import pytest
from unittest.mock import AsyncMock, MagicMock
from app.infrastructure.locks import profile_lock, LockAcquisitionTimeout

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
    assert first_args[1]["params"] == {"key": "profile_user123_course456"}
    # Verify RELEASE_LOCK call
    second_args = db.execute.call_args_list[1]
    assert "RELEASE_LOCK" in str(second_args[0][0])
    assert second_args[1]["params"] == {"key": "profile_user123_course456"}

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
