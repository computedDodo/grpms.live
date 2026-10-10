# School code uniqueness fix plan and working notes

## Status

This document records the work completed so far and the remaining steps needed to finish the school-code uniqueness fix safely.

The repo currently has the following relevant pieces:

- `app/models.py`
  - `School.code` is defined as `db.Column(db.String(6), nullable=True)`
  - this field was not protected against duplicates before the recent change
- `app/routes/superadmin.py`
  - `school_settings()` normalizes the submitted school code to uppercase and strips non-letters, but it does not check for duplicates before saving
- `app/routes/admin.py`
  - `_generate_admission_number()` uses the school prefix and school ID as part of the sequence calculation
- `migrations/versions/0003_school_code_subject_section.py`
  - adds the `schools.code` column without a uniqueness constraint

## What was done

I updated the `School` model in `app/models.py` to add the core validation helpers needed for the uniqueness fix:

- `School.normalize_code(raw_code)`
  - strips whitespace
  - converts to uppercase
  - removes all non-letter characters
  - keeps only the first 6 characters
  - returns `None` if there are no letters left

- `School.code_exists(code, exclude_school_id=None)`
  - checks whether a normalized school code already exists in the database
  - does a case-insensitive comparison
  - ignores the current school record when editing an existing school

- `School.code` field updated to include uniqueness metadata at the model layer

This means the app now has a reusable, consistent normalization and duplicate check for future validation work.

## Why this problem matters

The root issue is that school codes are currently not globally unique across all schools.

This creates a risk because the app uses codes like:

- `LAC`
- `RQA`
- `BHS`

as the prefix in admission numbers such as:

- `LAC/25/26/001`
- `RQA/25/26/001`

If two schools share the same code, the prefix can collide conceptually even though the current generator scopes the admissions by `school_id`. That still leaves a platform-wide quality and data-integrity issue because school codes should be unique across the platform.

## Remaining work required by you

### 1) Add the DB-level uniqueness constraint safely

Before adding a uniqueness constraint, check the production/dev database for existing duplicates.

Run this safety check in the working database first:

```sql
SELECT
  UPPER(code) AS normalized_code,
  COUNT(*) AS duplicate_count,
  GROUP_CONCAT(id) AS school_ids
FROM schools
WHERE code IS NOT NULL
GROUP BY UPPER(code)
HAVING COUNT(*) > 1;
```

If this returns rows, stop and resolve them manually before migrating.

Do not auto-rename existing schools or admission numbers.

If no duplicates are found, add a migration like the following pattern:

```python
"""Ensure school codes are globally unique."""

from alembic import op
import sqlalchemy as sa

revision = 'xxxx_school_code_unique'
down_revision = '2ef9e254bb24'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Normalize current values before constraint is added
    bind.execute(sa.text(
        "UPDATE schools SET code = UPPER(code) WHERE code IS NOT NULL"
    ))

    # Optional cleanup for non-letter characters:
    # bind.execute(sa.text(
    #     "UPDATE schools SET code = REGEXP_REPLACE(code, '[^A-Z]', '', 'g') WHERE code IS NOT NULL"
    # ))

    result = bind.execute(sa.text(
        """
        SELECT code, COUNT(*) AS cnt
        FROM schools
        WHERE code IS NOT NULL
        GROUP BY code
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    if result:
        raise RuntimeError(
            "Duplicate school codes detected. Resolve these before adding the unique constraint. "
            f"Conflicts: {result}"
        )

    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_schools_code', ['code'])


def downgrade():
    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.drop_constraint('uq_schools_code', type_='unique')
```

Important:
- only add the uniqueness constraint after duplicates are resolved
- do not apply this migration to production until the conflict list is reviewed

### 2) Enforce validation in the school settings route

The main app-level guard belongs in `app/routes/superadmin.py` inside `school_settings()`.

Add the following logic before saving the school:

```python
raw_code = request.form.get('code', '').strip()
if raw_code:
    normalized = School.normalize_code(raw_code)
    if not normalized:
        flash('School code must contain at least one letter (A-Z).', 'warning')
        return redirect(url_for('superadmin.school_settings'))

    if School.code_exists(normalized, exclude_school_id=school.id):
        existing_school = School.query.filter(
            db.func.upper(School.code) == normalized.upper()
        ).first()
        flash(
            f'School code "{normalized}" is already in use by "{existing_school.name}". '
            'Please choose a different code.',
            'danger'
        )
        return redirect(url_for('superadmin.school_settings'))

    school.code = normalized
else:
    school.code = None
```

This ensures:
- duplicate codes are rejected clearly
- case is normalized consistently
- valid submission includes only letters, max 6 characters
- editing the same record does not falsely fail

### 3) Preserve the admission number generator behavior

The generator in `app/routes/admin.py` is currently structured as:

- build prefix from school code
- query matching admission numbers by prefix and `school_id`
- increment sequence accordingly

This is good because it preserves the existing admission-number format and prevents reuse within the same school/session.

Do not change:
- the format
- the existing existing admission numbers
- the sequence logic by session
- any renumbering of current students

Just keep the generator as-is, unless you need an additional defensive comment or a helper for clarity.

### 4) Add focused tests

Add a small test file that verifies the rules below:

1. creating a school with a unique code succeeds
2. creating a school with an existing code fails
3. code comparisons are case-insensitive
4. updating a school's code to its own existing code succeeds
5. updating a school's code to another school's code fails
6. invalid characters and codes longer than 6 are handled correctly
7. admission-number generation remains compatible with existing records
8. duplicate admission numbers remain prevented
9. concurrent duplicate-code attempts are handled by the database uniqueness constraint

A minimal pytest pattern looks like this:

```python
import pytest
from app import db
from app.models import School


def test_school_code_case_insensitive_duplicate_check(app):
    school_a = School(name='One', code='LAC')
    db.session.add(school_a)
    db.session.commit()

    assert School.code_exists('lac') is True
    assert School.code_exists('LAC') is True


def test_school_code_rejects_duplicate(app):
    s1 = School(name='Alpha', code='RQA')
    s2 = School(name='Beta', code='RQA')
    db.session.add(s1)
    db.session.commit()
    db.session.add(s2)

    with pytest.raises(Exception):
        db.session.commit()
```

### 5) Ensure the database and app are aligned

After the migration and route validation are in place:

- run schema migration
- run the targeted tests
- confirm no invalid duplicates remain
- check a few UI flows in the SuperAdmin settings page

### 6) Do not do these things until the conflict check is complete

Do not do the following until duplicate school codes are resolved:

- do not add the uniqueness constraint blindly
- do not auto-rename schools
- do not rewrite admission numbers
- do not reset or delete production data
- do not deploy without manual review of duplicate conflicts

## Safety note

This repo cannot be fully verified end-to-end from the API-only view used here. I did not run migration or pytest in a real local environment, and I did not claim tests passed.

The current implementation is intentionally partial and designed to be a safe foundation for the rest of the work you are about to finish.

## Recommended next commands for your local environment

Run these in the repository checkout, in order:

```bash
# 1. inspect repository state
git status

# 2. check duplicate school codes before any migration
python - <<'PY'
from app import create_app, db
from app.models import School
app = create_app()
with app.app_context():
    rows = db.session.execute(
        db.text("""
            SELECT UPPER(code) AS normalized_code, COUNT(*) AS duplicate_count
            FROM schools
            WHERE code IS NOT NULL
            GROUP BY UPPER(code)
            HAVING COUNT(*) > 1
        """)
    ).fetchall()
    print(rows)
PY

# 3. add migration
flask db migrate -m "Enforce global unique school codes"

# 4. review the generated migration and adjust if needed

# 5. apply migration only after duplicates are resolved
flask db upgrade

# 6. run targeted tests
pytest -q
```

## Summary

The fix is now partially scaffolded:

- model-level normalization and duplicate detection are in place
- remaining work is centered around the database migration and the SuperAdmin validation route
- production safety requires duplicate-code audit before the unique constraint is added

This gives you a safe path to finish the remainder without risking existing records or revenue-critical data.

## Files involved

- `app/models.py`
- `app/routes/superadmin.py`
- `app/routes/admin.py`
- `migrations/versions/0003_school_code_subject_section.py`
- new migration to be created for uniqueness enforcement
- new tests to be added for the school-code and admission-number workflow
