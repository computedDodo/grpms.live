# Uniqueness fix — implementation sign‑off

This document is the formal sign-off artifact for the School-code uniqueness work described in `docs/changelog/uniqueness-proposal.md`.

Status
- Implementation completed and committed to the `main` branch in this repository (see commits below).
- Changes include application-level validation, a safe Alembic migration, focused tests, and documentation.

Summary of changes

1) Application validation
- File: `app/routes/superadmin.py`
- Behavior: Normalizes submitted codes (trim, uppercase, letters-only, max 6 chars). Rejects non-empty submissions that normalize to no letters. Performs a case-insensitive duplicate check excluding the current school when editing. Wraps commit in try/except to catch database IntegrityError and show a friendly message.

2) Model helpers
- File: `app/models.py`
- Behavior: Added `School.normalize_code(raw_code)` and `School.code_exists(code, exclude_school_id=None)` for consistent normalization and duplicate checks across the codebase. Marked model-level uniqueness/index metadata for `code`.

3) Database migration
- File: `migrations/versions/0004_enforce_school_code_uniqueness.py`
- Revision ID: `0004_enforce_school_code_uniqueness`
- Down-revision: `2ef9e254bb24`
- Behavior: Reads all non-empty codes and normalizes them (same rules as the app). If normalization yields duplicates (more than one school with the same normalized code), the migration fails loudly and lists conflicts — manual resolution required. If no conflicts, the migration updates normalized rows and creates unique constraint `uq_schools_code` on `schools.code` (NULLs allowed). Downgrade drops only that constraint.

4) Tests
- File: `tests/test_school_code.py`
- Behavior: Focused pytest cases covering creation, duplicate detection, case-insensitivity, updating-own-code, invalid normalization, and related checks.

5) Documentation
- File: `docs/school-code-uniqueness.md` (existing) — detailed runbook and audit steps.
- This sign-off doc is added at `docs/changelog/uniqueness-implementation.md`.

Commits (recent)
- 1a09dc02 — Add unique school code validation and normalization to the School model (app/models.py)
- 2cf53c25 — Document the school-code uniqueness fix status and guide the remaining work (docs/school-code-uniqueness.md)
- 008aa8d9 — Enforce school-code validation before saving settings and guard duplicate-key database collisions (app/routes/superadmin.py)
- 647a7df5 — Add Alembic migration to enforce unique normalized school.code (migrations/versions/0004_enforce_school_code_uniqueness.py)
- 891499a6 — Add focused tests covering school code normalization and duplicate validation (tests/test_school_code.py)

Next steps (must be run locally / in staging / production with care)
1. Run the conflict audit against the target DB (dev/staging/prod) using the SQL or the included Python audit script in `docs/school-code-uniqueness.md`.
2. If conflicts exist, resolve them manually (do not proceed). Document decisions.
3. Ensure a verified backup exists for production.
4. Run migration in staging and run tests: `flask db upgrade`, then `pytest -q`.
5. After staging verification and backups, run migration in production and monitor.

Acceptance & sign-off checklist
- [ ] Conflict audit run against production and zero conflicts reported
- [ ] Migration applied successfully in staging and smoke-tested
- [ ] Tests passing in CI/local
- [ ] Backup of production DB available and verified
- [ ] Stakeholder approval to run migration in production

If you need, I can open a PR with these commits and a description for reviewer sign-off, or prepare a minimal admin report to list any conflicting school rows for remediation. Please tell me which you prefer next.
