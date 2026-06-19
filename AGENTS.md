# Repo Agent Instructions

This repository uses a simple release rule:

1. When the app version changes, update both version locations together:
   - `app/main.py`
   - `reolink_enhanced_api/config.yaml`
2. Update the changelog in the same change:
   - `CHANGELOG.md`
   - `reolink_enhanced_api/CHANGELOG.md`
3. Keep the top-level user docs aligned if the visible product name or setup flow changes:
   - `README.md`
   - `INSTALL.md`
   - `QUICKSTART.md`

Release checks:

- The add-on manifest version must match the app version string.
- The changelog entry should describe the user-visible change, not internal implementation history.
- Do not publish a version bump without a changelog entry.

