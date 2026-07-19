#!/bin/bash
python3 -m pytest tests/test_evaluation_routes_refactored.py tests/test_evaluation_service_refactored.py tests/test_refresh_async.py tests/test_lock_async.py -v
