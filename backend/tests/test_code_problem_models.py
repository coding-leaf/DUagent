import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_private_code_problem_schema_exposes_owner_and_case_linkage():
    from app.models.code_problem import CodeProblem, CodeProblemTestCase
    from app.models.others import UserPersonalizedResource

    assert CodeProblem.__tablename__ == "code_problems"
    assert "owner_user_id" in CodeProblem.__table__.c
    assert "code_problem_id" in UserPersonalizedResource.__table__.c
    assert CodeProblemTestCase.__table__.c.problem_id.foreign_keys


def test_private_code_problem_keeps_reference_solution_outside_resource_model():
    from app.models.code_problem import CodeProblem
    from app.models.others import Resource

    assert "reference_solution" in CodeProblem.__table__.c
    assert "reference_solution" not in Resource.__table__.c
