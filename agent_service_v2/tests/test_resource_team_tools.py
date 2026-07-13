import asyncio
import json

from agent_service_v2.tools.resource_drafts import build_resource_draft_tools
from agent_service_v2.tools.resource_reviews import build_resource_review_tools


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        if path.endswith("/drafts"):
            return {"generation_id": "g1", "status": "drafted"}
        if path.endswith("/validation"):
            return {"generation_id": "g1", "status": "validated"}
        if path.endswith("/review"):
            return {"generation_id": "g1", "status": payload["decision"]}
        return {"resource_id": "r1", "status": "published"}


def _result(response):
    return json.loads(response.content[0].text)


def test_draft_validator_separates_hard_failures_from_warnings():
    client = FakeClient()
    tools = {tool.name: tool for tool in build_resource_draft_tools(client)}

    response = asyncio.run(
        tools["record_personalized_validation"].call(
            generation_id="g1",
            user_id="u1",
            course_id="c1",
            resource_type="diagram",
            content="flowchart TD\nA-->B",
        )
    )

    assert _result(response)["report"] == {
        "status": "passed",
        "validator": "typed_resource_validator",
        "hard_failures": [],
        "warnings": [],
    }


def test_reviewer_warnings_do_not_block_approval():
    client = FakeClient()
    tools = {tool.name: tool for tool in build_resource_review_tools(client)}

    response = asyncio.run(
        tools["review_personalized_resource"].call(
            generation_id="g1",
            user_id="u1",
            course_id="c1",
            hard_failures=[],
            warnings=["可增加更多边界用例"],
            summary="内容准确，可以发布并附带建议。",
        )
    )

    assert _result(response)["decision"] == "approved_with_advice"
    assert client.calls[-1][1]["warnings"] == ["可增加更多边界用例"]


def test_reviewer_only_rejects_when_hard_failures_exist():
    client = FakeClient()
    tools = {tool.name: tool for tool in build_resource_review_tools(client)}

    response = asyncio.run(
        tools["review_personalized_resource"].call(
            generation_id="g1",
            user_id="u1",
            course_id="c1",
            hard_failures=["deterministic_validation_failed"],
            warnings=[],
            summary="确定性验证未通过。",
        )
    )

    assert _result(response)["decision"] == "rejected"


def test_reviewer_cannot_treat_test_coverage_advice_as_hard_failure():
    client = FakeClient()
    tools = {tool.name: tool for tool in build_resource_review_tools(client)}

    response = asyncio.run(
        tools["review_personalized_resource"].call(
            generation_id="g1",
            user_id="u1",
            course_id="c1",
            hard_failures=["测试用例不够充分"],
            warnings=[],
            summary="建议增加更多测试。",
        )
    )

    assert _result(response)["decision"] == "approved_with_advice"
    assert client.calls[-1][1]["hard_failures"] == []
    assert client.calls[-1][1]["warnings"] == ["测试用例不够充分"]
