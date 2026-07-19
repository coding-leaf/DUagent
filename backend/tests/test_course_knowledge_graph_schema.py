from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint

from app.models.others import CourseKnowledgeGraph


def test_course_knowledge_graph_metadata_matches_versioned_schema() -> None:
    table = CourseKnowledgeGraph.__table__

    expected_columns = {
        "version",
        "is_active",
        "source_type",
        "generation_strategy",
        "metrics",
        "parent_graph_id",
    }
    assert expected_columns <= set(table.columns.keys())

    assert table.c.version.default.arg == 1
    assert table.c.version.nullable is False
    assert table.c.is_active.default.arg is True
    assert table.c.is_active.nullable is False
    assert table.c.source_type.default.arg == "manual_import"
    assert table.c.source_type.nullable is False
    assert table.c.generation_strategy.default.arg == "legacy_outline"
    assert table.c.generation_strategy.nullable is False
    assert table.c.metrics.nullable is True
    assert table.c.parent_graph_id.nullable is True

    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_constraints["uk_course_version"] == ("course_id", "version")

    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in table.indexes
        if isinstance(index, Index)
    }
    assert indexes["idx_course_active"] == ("course_id", "is_active", "is_deleted")
    assert indexes["idx_parent_graph_id"] == ("parent_graph_id",)

    foreign_keys = {
        constraint.name: (
            tuple(column.name for column in constraint.columns),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert foreign_keys["fk_ckg_parent_graph"] == (
        ("parent_graph_id",),
        ("course_knowledge_graphs.id",),
    )
