from __future__ import annotations

import pytest

from agent_service_v2.tools.contracts import outcome_for_status


@pytest.mark.parametrize(
    "status",
    ["available", "published", "ok", "success"],
)
def test_terminal_success_statuses_map_to_success(status):
    assert outcome_for_status(status) == "success"


@pytest.mark.parametrize(
    "status",
    ["drafted", "validated", "approved", "approved_with_advice"],
)
def test_generation_lifecycle_statuses_map_to_success(status):
    """Each completed pipeline step is a successful tool call.

    The frontend `chatStreamEvents.js` reducer turns a tool card into an error
    card when `outcome === "failure"`, so intermediate lifecycle statuses must
    not be classified as failures.
    """
    assert outcome_for_status(status) == "success"


@pytest.mark.parametrize("status", ["empty", "not_found"])
def test_empty_statuses_map_to_neutral(status):
    assert outcome_for_status(status) == "neutral"


def test_degraded_status_maps_to_warning():
    assert outcome_for_status("degraded") == "warning"


@pytest.mark.parametrize(
    "status",
    ["rejected", "unavailable", "delivery_incomplete", "delivery_failed", "error", "failed"],
)
def test_failure_statuses_map_to_failure(status):
    assert outcome_for_status(status) == "failure"


def test_framework_error_wins_over_a_success_status():
    assert outcome_for_status("published", framework_error=True) == "failure"


def test_unknown_and_missing_statuses_fail_closed():
    assert outcome_for_status("something_new") == "failure"
    assert outcome_for_status(None) == "success"
    assert outcome_for_status("") == "success"
