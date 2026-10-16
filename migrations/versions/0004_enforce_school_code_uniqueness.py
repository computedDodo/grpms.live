"""Enforce unique school codes without modifying existing values.

Revision ID: 0004_enforce_school_code_uniqueness
Revises: 2ef9e254bb24
Create Date: 2026-10-16
"""

import re

from alembic import op
from sqlalchemy import inspect
from sqlalchemy.sql import text

revision = "0004_enforce_school_code_uniqueness"
down_revision = "2ef9e254bb24"
branch_labels = None
depends_on = None


def normalize(value):
    if value is None:
        return None

    code = re.sub(r"[^A-Za-z]", "", str(value).strip().upper())[:6]
    return code or None


def upgrade():
    bind = op.get_bind()

    rows = bind.execute(
        text(
            "SELECT id, code FROM schools "
            "WHERE code IS NOT NULL AND code <> ''"
        )
    ).fetchall()

    normalized_codes = {}
    needs_review = []

    for row in rows:
        school_id, existing_code = row[0], row[1]
        normalized = normalize(existing_code)

        if normalized != existing_code:
            needs_review.append(
                (school_id, existing_code, normalized)
            )

        if normalized:
            normalized_codes.setdefault(normalized, []).append(school_id)

    conflicts = {
        code: ids
        for code, ids in normalized_codes.items()
        if len(ids) > 1
    }

    if needs_review or conflicts:
        details = []

        if needs_review:
            details.append(
                "Codes needing manual review (school_id, existing, "
                f"normalized): {needs_review}"
            )

        if conflicts:
            details.append(
                f"Duplicate normalized codes (code: school_ids): {conflicts}"
            )

        raise RuntimeError(
            "Cannot enforce school-code uniqueness. "
            "No school codes were changed. Resolve these issues manually. "
            + " | ".join(details)
        )

    inspector = inspect(bind)

    # Check the actual database schema before creating a unique constraint.
    existing_unique_indexes = {
        index["name"]
        for index in inspector.get_indexes("schools")
        if index.get("unique") and index.get("name")
    }

    existing_unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("schools")
        if constraint.get("name")
    }

    if (
        "uq_schools_code" not in existing_unique_indexes
        and "uq_schools_code" not in existing_unique_constraints
    ):
        with op.batch_alter_table("schools", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_schools_code",
                ["code"],
            )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    indexes = inspector.get_indexes("schools")
    constraints = inspector.get_unique_constraints("schools")

    # Do not remove a pre-existing index during downgrade.
    # Only remove the constraint if it is represented as a constraint
    # and not merely as a pre-existing MySQL/MariaDB unique index.
    constraint_names = {
        item["name"]
        for item in constraints
        if item.get("name")
    }

    index_names = {
        item["name"]
        for item in indexes
        if item.get("name") and item.get("unique")
    }

    if (
        "uq_schools_code" in constraint_names
        and "uq_schools_code" not in index_names
    ):
        with op.batch_alter_table("schools", schema=None) as batch_op:
            batch_op.drop_constraint(
                "uq_schools_code",
                type_="unique",
            )
