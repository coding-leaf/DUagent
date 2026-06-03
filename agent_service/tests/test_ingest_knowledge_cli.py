import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_service.tools.ingest_knowledge import main

def test_main_directory_not_exists(caplog):
    with patch.object(sys, "argv", ["ingest_knowledge.py", "/non/existent/path"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
    
    assert "Path does not exist" in caplog.text or "not exist" in caplog.text

def test_main_empty_directory(caplog):
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.object(sys, "argv", ["ingest_knowledge.py", temp_dir]):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 1
        
        assert "No supported files" in caplog.text or "empty" in caplog.text

def test_main_exception(caplog):
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "dummy.md").touch()
        with patch("agent_service.tools.ingest_knowledge.ingest_course_knowledge", side_effect=Exception("Mocked Error")):
            with patch.object(sys, "argv", ["ingest_knowledge.py", temp_dir]):
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 1
            
        assert "Mocked Error" in caplog.text

def test_main_single_file_unsupported(caplog):
    with tempfile.TemporaryDirectory() as temp_dir:
        unsupported_file = Path(temp_dir) / "foo.docx"
        unsupported_file.touch()
        with patch.object(sys, "argv", ["ingest_knowledge.py", str(unsupported_file)]):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 1
        assert "Unsupported file type" in caplog.text

def test_main_success(caplog):
    import logging
    caplog.set_level(logging.INFO)
    from agent_service.tools.ingest_knowledge import KnowledgeIngestionResult
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "dummy.md").touch()
        mock_result = KnowledgeIngestionResult(course_id="dummy", chunk_count=5, duration_seconds=1.23)
        with patch("agent_service.tools.ingest_knowledge.ingest_course_knowledge", return_value=mock_result):
            with patch.object(sys, "argv", ["ingest_knowledge.py", temp_dir]):
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 0
        assert "Ingestion completed for course_id=dummy: 5 chunks" in caplog.text

def test_main_keyboard_interrupt(caplog):
    import logging
    caplog.set_level(logging.WARNING)
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "dummy.md").touch()
        with patch("agent_service.tools.ingest_knowledge.ingest_course_knowledge", side_effect=KeyboardInterrupt()):
            with patch.object(sys, "argv", ["ingest_knowledge.py", temp_dir]):
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 1
        assert "interrupted by user" in caplog.text

def test_main_verbose(caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    from agent_service.tools.ingest_knowledge import KnowledgeIngestionResult
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "dummy.md").touch()
        mock_result = KnowledgeIngestionResult(course_id="dummy", chunk_count=5, duration_seconds=1.23)
        with patch("agent_service.tools.ingest_knowledge.ingest_course_knowledge", return_value=mock_result):
            with patch.object(sys, "argv", ["ingest_knowledge.py", temp_dir, "--verbose"]):
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 0
        assert "Starting ingestion for" in caplog.text

