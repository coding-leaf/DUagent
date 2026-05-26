def test_smoke_all_imports_and_main_callable() -> None:
    from agent_service.tools import smoke_all

    assert callable(smoke_all.main)


def test_smoke_all_main_returns_int() -> None:
    from agent_service.tools.smoke_all import main

    result = main()
    assert isinstance(result, int)
    assert result == 0
