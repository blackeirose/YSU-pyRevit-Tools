SHEET / VIEW TOOLS
Version: 1.0.0

Purpose:
Deletes the sheet(s) you have selected in the Project Browser, along with
any views placed only on those sheets. Views, legends, and schedules that
are also placed on other sheets are automatically detected and retained.
Before deleting anything, a preview dialog lists exactly what will be
deleted and what will be kept, and you must confirm.

Usage:
1. Select one or more sheets in the Project Browser.
2. Click "Delete Sheets + Views" on the YSU Tools tab (Views & Sheets
   panel).
3. Review the preview: sheets to delete, views to delete, and shared
   views/legends/schedules that will be retained.
4. Confirm to proceed, or cancel to make no changes.
5. If the active view is one of the items being deleted, the tool
   automatically switches to another open or available view first.

Installation:
1. Download the ZIP.
2. Extract it. You will get a folder named "YSU Tools.extension".
3. Copy the "YSU Tools.extension" folder into the pyRevit extensions
   folder configured for your installation (use pyRevit > Settings to
   find or add an extensions search path if you are not sure where
   that is).
4. Reload pyRevit (pyRevit tab > Reload) or restart Revit.
5. Confirm the "YSU Tools" tab appears with a "Views & Sheets" panel
   containing the "Delete Sheets + Views" button.

Supported Revit version(s):
Revit 2020 through 2026. The underlying element-id handling is written
specifically to stay stable across this API range.

Supported pyRevit version(s):
pyRevit 4.8 and later (CPython3 or IronPython engine).

Notes / limitations:
- This tool is destructive: confirmed sheets and their exclusively-placed
  views are permanently deleted in a single transaction. Revit Undo may
  not be available afterward (e.g. after a sync in a workshared model) —
  verify your backup and worksharing status before confirming.
- Requires at least one sheet to be selected in the Project Browser
  before running.
- Only the "Delete Sheets + Views" tool (Views & Sheets panel) is
  included in this package, along with the small shared "ysu_sheets"
  library module it depends on. Other tools from the full YSU Tools
  extension are not part of this download.

Uninstall:
Delete the installed "YSU Tools.extension" folder from your pyRevit
extensions directory and reload pyRevit.
