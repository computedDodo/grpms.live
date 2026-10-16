GRPMS DevOps Handover — Urgent School-Code Uniqueness Fix

Priority: URGENT — implement and verify tonight
Project: GRPMS (computedDodo/grpms.live)
Objective: Prevent two schools from using the same school code, at both application and database levels.

1. Confirmed findings

Our investigation established the following:

A. Current model — app/models.py

code = db.Column(db.String(6), nullable=True)

The field permits duplicate codes because it has no declared uniqueness constraint.

B. Actual local database schema

We inspected grpms_dev using:

SHOW CREATE TABLE schools;

The relevant output was:

`code` varchar(6) DEFAULT NULL,
PRIMARY KEY (`id`)

Finding: There is no unique index or constraint on schools.code.

C. Existing data

Our local database currently contains:

School ID	School name	Code

1	Grade6ix Demo Academy	DMA


No duplicate appears in this local snapshot. Production must be checked separately.

D. School settings route — app/routes/superadmin.py

The existing code normalizes submitted school codes:

raw_code = request.form.get('code', '').strip().upper()

if raw_code:
    import re
    clean_code = re.sub(r'[^A-Z]', '', raw_code)[:6]
    if clean_code:
        school.code = clean_code

Problem: The route does not check whether another school already owns the code.

E. Migration history

migrations/versions/0003_school_code_subject_section.py added the code column as nullable String(6) without enforcing uniqueness.

The local database reports migration revision 2ef9e254bb24 as its current head. This does not establish production's migration state.


---

FIX 1 — Application-Level Validation

Files primarily involved:

app/models.py

app/routes/superadmin.py


Requirements

1. Implement reusable school-code normalization and duplicate-checking logic.


2. Normalize codes consistently:

Trim whitespace.

Convert letters to uppercase.

Keep only A–Z.

Limit codes to six characters.



3. Reject a code already assigned to another school.


4. When editing a school, exclude that school's own ID from the duplicate check.


5. If a non-empty submission contains no valid letters after normalization, display a clear validation message.


6. Preserve the existing behavior whereby an empty submission does not erase the school's current code.


7. Validate the code before committing any other form changes. A failed validation must not partially save the settings.


8. Once the database constraint exists, handle duplicate-key IntegrityError exceptions safely: roll back the transaction and display a friendly error.


9. Do not modify admission-number generation, coupon logic, results processing, or unrelated features.



Acceptance tests

Verify that:

School A can register code LAC.

School B cannot register LAC.

School B cannot bypass the check using lac.

School A can save its existing code without a false duplicate warning.

Invalid non-empty codes are rejected clearly.

Blank code submissions do not erase existing codes.

Other settings continue saving normally when validation succeeds.



---

FIX 2 — Database-Level Uniqueness

Primary task: Create a new Alembic migration that adds a unique constraint or unique index to schools.code.

Do not edit an already-applied migration to introduce this change.

Before creating or applying the migration

Step 1: Check existing codes

Run against the target database:

SELECT id, name, code
FROM schools
ORDER BY id;
**Note:** I already passed this stage and got the required resut below:
~/grpms.live $ mariadb -u root grpms_dev -e "SELECT id, name, code FROM schools ORDER BY id;"
+----+-----------------------+------+
| id | name                  | code |
+----+-----------------------+------+
|  1 | Grade6ix Demo Academy | DMA  |
+----+-----------------------+------+


Step 2: Audit duplicates

Check for duplicates according to the intended normalization rules, including case-insensitive collisions and different values that normalize to the same code.

If conflicts exist, stop and report them to the owner. Do not automatically rename school codes.

Step 3: Back up the database

Take a verified backup before applying any production schema changes.

Step 4: Verify the production environment

Inspect the actual production schema and migration revision independently. Do not assume PythonAnywhere has the same schema or data as local grpms_dev.
**Note:** All these step 1,2,3 and 4 is passed, I comfirm everythimg and were good to go.


Migration requirements

Enforce uniqueness for non-NULL school codes.

Preserve the existing six-character limit unless a schema change is explicitly approved.

Do not change String(6) to String(30) without approval.

Do not make the column NOT NULL without confirming that all existing schools have valid codes and obtaining approval for that behavior. (Currently theres only one same school on both tbe production and tbe development sever with same data)

Confirm production database collation and ensure the uniqueness rules match application normalization.

Fail safely if conflicting data exists.

Never automatically rewrite existing codes to resolve conflicts.

Ensure the downgrade removes only the constraint or index introduced by this migration.

I would Test the migration against a disposable database or verified clone before production.


Important: The local MariaDB collation is utf8mb3_uca1400_ai_ci, which is case- and accent-insensitive. Production may use a different collation (Honestly im not familiar with this), so we might like to verify itif necessar.


---

Execution Order — Tonight

Order	Task	Required outcome

1	Record Git status and current commit	Existing work is protected
2	Implement application validation	Duplicate codes rejected before saving
3	Add targeted tests	Validation behavior verified
4	Create a new migration	Database uniqueness enforced
5	Test migration and review diff	No unrelated changes
6	Back up production database	Recoverable backup available
7	Audit production codes and schema	No unresolved conflicts
8	Apply migration after checks and approval	Production constraint installed
9	Deploy application changes	Updated application running
10	Smoke-test school-code assignment	Duplicate attempts rejected


Critical safeguards

Our earlier Termux Git status showed these unrelated local changes:

M app/models1.py
M app/routes/student.py
?? Local_emergency_reset.py
?? beta_backup_before_seed.sql

I wiuld Preserve these files and changes. Do not run git reset --hard, git clean, or commands that discard unrelated work.

i would not apply a production migration until the database is backed up and the duplicate audit has passed.

Final deliverables from DevOps (you)

After completing the work, report:

1. Files changed.


2. Commit hash.


3. Migration revision.


4. Backup location.(i got this)


5. Test results.


6. Production schema verification.


7. Confirmation that duplicate codes are rejected.


8. Confirmation that existing school records remain intact.



Definition of done: Application validation and database-level uniqueness are both implemented, tested, and verified in production without losing existing data or disturbing unrelated work.
