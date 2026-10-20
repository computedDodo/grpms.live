# Teacher score-entry draft autosave

## Purpose

This feature keeps the teacher’s score entry values in the browser even if the page is refreshed before the final submit. It prevents accidental loss of unsaved score data while the teacher is entering marks.

## File updated

- `app/templates/teacher/score_entry.html`

## How it works

The page uses `localStorage` to save the form values keyed by the current teacher allocation ID. When the page loads, it restores those values automatically. When the teacher submits the form, the saved draft is cleared.

This is a client-side safety net only. It does not store data on the server until the final form submission.

## Exact implementation snippet

### Storage key and status element

```html
<script>
document.addEventListener('DOMContentLoaded', function () {
  const storageKey = 'grpms_score_entry_{{ allocation.id }}';
  const form = document.querySelector('form');
  const inputs = document.querySelectorAll('.score-input');
  const draftStatus = document.getElementById('draft-status');
```

### Draft status UI

```html
<div style="display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap;">
  <span class="g6-text-sm g6-muted">
    <i class="fas fa-info-circle"></i>
    Scores are clamped to their maximum automatically. Blank fields save as 0.
  </span>
  <span id="draft-status" class="g6-text-sm" style="display:inline-flex; align-items:center; gap:0.35rem; color:var(--slate-500); font-weight:600;">
    <i class="fas fa-circle-notch" style="font-size:0.7rem;"></i>
    Draft autosave ready
  </span>
</div>
```

### Save draft to localStorage

```javascript
function saveDraft() {
  const payload = {};
  inputs.forEach(inp => {
    if (inp.value !== '') {
      payload[inp.name] = inp.value;
    }
  });

  try {
    if (Object.keys(payload).length === 0) {
      localStorage.removeItem(storageKey);
      if (draftStatus) {
        draftStatus.innerHTML = '<i class="fas fa-circle-notch" style="font-size:0.7rem;"></i> Draft autosave ready';
        draftStatus.style.color = 'var(--slate-500)';
      }
      return;
    }

    localStorage.setItem(storageKey, JSON.stringify(payload));
    setDraftStatus('Draft saved automatically', 'var(--emerald-600)');
  } catch (err) {
    console.warn('Failed to save score-entry draft:', err);
  }
}
```

### Restore draft on page refresh

```javascript
function restoreDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
    if (!saved || typeof saved !== 'object') return;

    inputs.forEach(inp => {
      if (saved[inp.name] !== undefined) {
        inp.value = saved[inp.name];
      }
    });

    setDraftStatus('Draft restored automatically', 'var(--blue-600)');
  } catch (err) {
    console.warn('Failed to restore score-entry draft:', err);
    try {
      localStorage.removeItem(storageKey);
    } catch (clearErr) {
      console.warn('Failed to clear broken score-entry draft:', clearErr);
    }
  }

  inputs.forEach(inp => updateTotal(inp.dataset.student));
}
```

### Clear saved draft on successful submit

```javascript
if (form) {
  form.addEventListener('submit', function () {
    try {
      localStorage.removeItem(storageKey);
    } catch (err) {
      console.warn('Failed to clear draft on submit:', err);
    }
  });
}
```

## Notes

- This feature is intentionally client-side only.
- It does not replace server-side saving; the actual data is only committed when the teacher submits the form.
- It is scoped per allocation, so score drafts stay isolated per subject/class assignment.
- The feature is designed to survive a browser refresh but not a browser wipe or cross-device transfer.

## Verification status

I confirmed the file in the repo contains the autosave logic and the status indicator. I did not run a browser-level verification in this session, so I am not claiming a live UI pass beyond the repository contents review.
