# Admin Students Page Mobile Responsiveness

## Purpose

This document records the mobile-friendly update added to the admin student management page so it behaves correctly on phones and tablets without affecting other templates in the application.

## Updated file

- `app/templates/admin/students.html`

## What was changed

The page was updated to:

- collapse the desktop two-column layout into a single-column layout on smaller screens
- keep a fixed bottom navigation for mobile users
- stack the table content into a cleaner mobile-friendly card layout
- scope all styling to this page using `#admin-students-page` so it does not leak into other templates

## Why this is safe

The styling is intentionally wrapped in a page-specific parent ID, so the rules only apply to this template:

```html
<div id="admin-students-page">
  ...
</div>
```

and the CSS uses selectors like:

```css
#admin-students-page .student-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}
```

This ensures that global selectors such as `form`, `table`, or `.g6-table-responsive` are not accidentally changed across the rest of the application.

## Exact responsive logic

### Layout collapse on tablet/mobile

```css
@media (max-width: 900px) {
  #admin-students-page .student-layout {
    grid-template-columns: 1fr;
  }

  #admin-students-page {
    padding-bottom: calc(var(--student-nav-height) + 1rem);
  }
}
```

### Mobile table stacking

```css
@media (max-width: 640px) {
  #admin-students-page .g6-table-responsive table,
  #admin-students-page .g6-table-responsive thead,
  #admin-students-page .g6-table-responsive tbody,
  #admin-students-page .g6-table-responsive th,
  #admin-students-page .g6-table-responsive td,
  #admin-students-page .g6-table-responsive tr {
    display: block;
    width: 100%;
  }

  #admin-students-page .g6-table-responsive thead {
    display: none;
  }

  #admin-students-page .g6-table-responsive tbody tr {
    background: #fff;
    border: 1px solid var(--slate-200, #e2e8f0);
    border-radius: 12px;
    padding: 0.75rem;
    margin-bottom: 0.75rem;
  }

  #admin-students-page .g6-table-responsive td {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    padding: 0.45rem 0;
    border: 0;
    width: 100%;
  }

  #admin-students-page .g6-table-responsive td::before {
    content: attr(data-label);
    display: block;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--slate-500, #64748b);
  }
}
```

### Fixed bottom mobile navigation

```html
<nav class="admin-students-mobile-nav" aria-label="Student mobile navigation">
  <a href="#manual-enrollment"><i class="fas fa-user-plus"></i><span>Enroll</span></a>
  <a href="#bulk-upload"><i class="fas fa-upload"></i><span>Upload</span></a>
  <a href="#student-directory"><i class="fas fa-users"></i><span>Directory</span></a>
</nav>
```

```css
#admin-students-page .admin-students-mobile-nav {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: 10px;
  z-index: 40;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  background: var(--student-nav-bg);
  border: 1px solid var(--student-nav-border);
  box-shadow: var(--student-nav-shadow);
  border-radius: 14px;
  padding: 0.5rem;
  backdrop-filter: blur(10px);
}
```

## Notes

- The design remains desktop-friendly on large screens.
- On smaller screens, the form and directory behave like a mobile app layout.
- The bottom navigation is a convenience improvement, not a replacement for the main desktop navigation.
- All changes are isolated to this template to reduce cross-template regressions.

## Verification

This file documents the implemented page-scoped responsive changes in `app/templates/admin/students.html`. A live browser verification was not executed in this session, so this is a code-level documentation of the implemented change rather than a visual QA confirmation.
