import pytest
from app.services.profile_presenters import profile_data, _default_profile

def test_profile_presenters_data_default():
    formatted = profile_data(None, "course456", None)
    assert formatted["guidance_level_current"] == "L2"
    assert formatted["modal_preference"] == _default_profile["modal_preference"]
    assert formatted["discipline_badge"] == _default_profile["discipline_badge"]
    assert len(formatted["dimensions"]) == 4
    assert formatted["resource_preference_summary"] == "未设置偏好"
