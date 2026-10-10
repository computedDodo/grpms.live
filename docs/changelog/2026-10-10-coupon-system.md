# GRPMS Development Update — Coupon System

**Date:** 2026-10-10  
**Project:** GRPMS V2  
**Repository:** https://github.com/computeddodo/grpms.live  
**Environment:** Development  
**Production deployment:** Not authorized by this record  
**Status:** Implementation committed previously; documentation added in this update

---

## 1. Objective

Improve the GRPMS report-card coupon system so students can activate
report cards for earlier academic terms without bypassing the required
activation sequence.

The system must preserve the existing report-release restrictions and
must not modify transcript coupon behavior.

## 2. Requirements

### 2.1 Sequential term activation

Students must activate the required earlier terms before accessing
subsequent terms.

The intended sequence is:

First Term → Second Term → Third Term

This sequence continues across academic sessions rather than resetting
at the beginning of each new session.

### 2.2 Historical term activation

A student who did not activate an earlier term's coupon at the time
must still be able to activate that term later, provided the required
prerequisite terms have been activated.

For example, a student must be able to request and activate a First
Term coupon after the school has moved into Second or Third Term.

Historical activation must not allow students to skip prerequisite
terms.

### 2.3 Coupon generation

Platform Administrators can select the relevant school, academic
session, and term when generating report-card coupons.

Coupon generation for historical terms is supported by the intended
workflow.

Coupon generation remains restricted to the Platform Administrator.

### 2.4 Coupon ownership and validation

A coupon must remain associated with its intended school and term.

The system must reject coupons belonging to another school and prevent
duplicate activation of the same student/term.

Once a term is activated, that activation remains recorded.

### 2.5 Report-release restrictions

Existing result-release checks must remain in effect.

Activating a coupon must not automatically bypass a school's
report-release restrictions.

### 2.6 Transcript coupons

Transcript coupon behavior is outside the scope of this change and
must remain unchanged.

---

## 3. Implementation areas

The coupon work involved the following application areas:

- `app/models.py`
  - Coupon and coupon-activation model behavior.

- `app/routes/student.py`
  - Coupon redemption and validation.
  - Historical term activation.
  - Sequential prerequisite checks.
  - Report access restrictions.

- `app/routes/platform.py`
  - Platform Administrator coupon-generation workflow.
  - Selection of historical academic terms.

- `app/templates/platform/generate_coupons.html`
  - School and academic-term selection in the coupon-generation interface.

Confirm the final Git diff before treating this list as a complete
record of the committed changes.

---

## 4. Important constraints

The following functionality is outside the scope of this update:

- Admission-number generation.
- Student promotion and promotion reversal.
- Class-weight configuration.
- Score computation and ranking.
- Transcript coupon logic.
- Unrelated school settings.
- Production database changes.

These areas must not be modified as part of future coupon maintenance
unless a separate change is explicitly planned.

---

## 5. Development and deployment policy

Development changes must be tested before production deployment.

A successful GitHub push does not mean that the change has been
deployed to PythonAnywhere.

Before production deployment:

1. Review the final Git diff.
2. Confirm that the intended changes are committed.
3. Run available tests.
4. Perform relevant manual tests in development.
5. Confirm that production configuration and database requirements
   have been reviewed.
6. Back up production data before any operation that could affect it.
7. Deploy only after explicitly approving the release.

---

## 6. Verification record

Record the actual results before release.

- [ ] Historical term coupon generation verified.
- [ ] First Term activation verified.
- [ ] Second Term activation requires First Term activation.
- [ ] Third Term activation requires earlier required terms.
- [ ] Cross-session prerequisites verified.
- [ ] Wrong-school coupon rejected.
- [ ] Duplicate student/term activation rejected.
- [ ] Result-release restrictions preserved.
- [ ] Transcript coupon behavior unchanged.
- [ ] Existing automated tests pass.
- [ ] Production deployment separately reviewed.

Do not mark a test as passed unless it has actually been performed.

---

## 7. Related Git history

Previously reported commit:

`7363ca2` — `models with the new coupon feature aware`

Related earlier commit:

`21cab79` — `Fix historical term coupon selection`

Verify the current repository history before relying on these identifiers
as the complete history of the implementation.

---

## 8. Follow-up work

Separate issues identified during development:

1. Prevent school admission-code collisions across schools.
2. Investigate promotion-reversal behavior.
3. Investigate class-weight and promotion transitions between
   Nursery, Primary, JSS, and SS.

These are separate tasks and must not be bundled into the coupon-system
change without review.

---

## 9. Change history

### 2026-10-10

- Prepared a permanent Markdown record for the coupon-system work.
- Production deployment remains a separate decision.
- Future development changes should have their own dated records.
