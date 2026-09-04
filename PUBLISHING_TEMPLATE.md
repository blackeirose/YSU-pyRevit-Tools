# pyRevit Tool Publishing Template

Use this checklist when publishing a new YSU pyRevit tool.

## 1. Inspect the source

- Confirm the tool folder and actual pyRevit bundle structure.
- Identify scripts, icons, config files, and shared dependencies.
- Verify whether the tool can run standalone.
- Do not package an incomplete tool or omit required shared modules.

## 2. Package the smallest valid extension

Preserve pyRevit's `.extension / .tab / .panel / .pushbutton` structure.

Preferred approach:

- Reuse `YSU Tools.extension` when the tool belongs to the shared YSU Tools extension.
- Include only the required tab/panel/tool files and dependencies.
- Do not flatten folders.
- Exclude temporary files, local paths, credentials, and development artifacts.

Recommended ZIP naming:

`YSU-<Tool-Name>-v1.0.0.zip`

## 3. Include installation documentation

Every ZIP should contain `README.txt` or `INSTALLATION.txt` with:

- Tool name
- Version
- Purpose
- Supported Revit version(s)
- Supported pyRevit version(s)
- Installation steps
- Known limitations
- Uninstall steps

Basic installation instructions:

1. Download the ZIP.
2. Extract the `.extension` folder.
3. Copy it into the pyRevit extensions directory configured for the user's installation.
4. Reload pyRevit or restart Revit.
5. Confirm the tool appears in the ribbon.

Do not present one Windows path as universally correct; pyRevit extension locations may be customized.

## 4. Version and release

If the tool has no previous version, start at `v1.0.0`.

Use one version consistently across:

- ZIP filename
- README / installation file
- Landing page
- GitHub Release title
- Git tag

Recommended tag pattern:

`<toolname>-v1.0.0`

## 5. Publish a GitHub Release

Repository:

`blackeirose/YSU-pyRevit-Tools`

For each release:

- Create the version tag.
- Create a GitHub Release.
- Attach the ZIP as a release asset.
- Add a short purpose, compatibility, installation summary, and limitations.
- Confirm the ZIP is publicly downloadable without authentication when the landing page is intended for public users.

## 6. Create the stable landing page

Public URL pattern:

`https://tools.ycsu.cc/pyrevit/<toolname>/`

Keep the page simple. Include:

- Tool name
- Short purpose
- Version
- Revit compatibility
- pyRevit compatibility
- `Download ZIP` button
- Installation instructions

The Download button should point to the GitHub Release asset, not to a temporary local file.

Do not build a separate Tools homepage, backend, login system, installer, or auto-update feature unless specifically requested.

## 7. Hub integration

The Workflow Hub is the discovery layer.

Recommended pattern:

`HUB planet/card` → `tools.ycsu.cc/pyrevit/<toolname>/` → `GitHub Release ZIP`

Use the stable `tools.ycsu.cc` landing-page URL in the Hub rather than linking directly to a version-specific ZIP.

## 8. Validation before release

Check all of the following:

- ZIP extracts successfully.
- pyRevit extension structure is valid.
- Required scripts, icons, and dependencies are included.
- README / installation file is included.
- No machine-specific absolute paths, secrets, temp files, or unrelated source files are packaged.
- Landing page returns 200 and renders correctly.
- Download button downloads the intended ZIP without authentication.
- GitHub Release version matches the landing page and README.
- Existing `https://tools.ycsu.cc/PlumbingChart/` still works.
- Existing Hub routes remain unaffected.

Do not claim a Revit functional test passed unless the tool was actually tested inside Revit.

## Reference implementation

Revision Cleanup is the first approved publishing reference:

- Landing page: `https://tools.ycsu.cc/pyrevit/revisioncleanup/`
- Release tag pattern: `revisioncleanup-v1.0.0`
- ZIP pattern: `YSU-Revision-Cleanup-v1.0.0.zip`

Future pyRevit tools should follow this same publishing pattern unless there is a clear technical reason to deviate.
