# Candidate validation boundary

Source version: 0.2.0-candidate. Source commit: 43906e98b14c8c34b3e19954d22b3bd5b8214a43.

- PASS (2026-10-08): nine source files match the configured loaded extension and the retained installation receipt, by SHA-256.
- PASS: independent source/dependency/privacy review for publishing these candidate source files only.
- Historical only: 102 simulated unit checks, IronPython compile and 26 WPF checks; not rerun for this publication.
- NOT VERIFIED: native Revit 2026 acceptance of this 0.2.0 version.
- HOLD: production ZIP / formal Release. Older-version user experience does not satisfy this gate.

Required next check in an isolated Revit 2026 document: Create, Update Current, Update All, persisted category/exclusion choices, cancellation, scan-error preservation, Undo and manual save/reopen, label/RGB and main View Range/Crop scope. Record the exact source hashes and each outcome. Never automatically Save/Sync a company model.

Private historical journals, user conversations, view names, element IDs and local machine paths are intentionally excluded from this public source archive.
