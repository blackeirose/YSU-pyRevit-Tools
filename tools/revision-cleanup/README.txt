REVISION CLEANUP
Version: 1.0.0

Purpose:
Purges all Revision Cloud Tags and Revision Clouds from the active Revit
project and deletes every Revision definition except the first, which is
cleared and kept as a blank placeholder (Revit requires at least one
Revision to remain). A confirmation dialog shows counts before anything is
deleted, and the whole operation runs as a single undoable transaction.

Installation:
1. Download the ZIP.
2. Extract it. You will get a folder named "YSU Tools.extension".
3. Copy the "YSU Tools.extension" folder into the pyRevit extensions
   folder configured for your installation (use pyRevit > Settings to find
   or add an extensions search path if you are not sure where that is).
4. Reload pyRevit (pyRevit tab > Reload) or restart Revit.
5. Confirm the "YSU Tools" tab appears with a "Cleanup" panel containing
   the "Purge All Revisions" button.

Supported Revit version(s):
Revit 2019 and later (standard pyRevit-supported Revit API, no
version-specific calls).

Supported pyRevit version(s):
pyRevit 4.8 and later (CPython3 or IronPython engine).

Notes / limitations:
- This tool is destructive: it permanently deletes revision clouds, tags,
  and revision definitions from the active document. Use Revit Undo
  immediately after running if the result is not what you expected.
- Elements that are owned by another user in a workshared model, or that
  are otherwise protected, may fail to delete; the tool reports these in
  the pyRevit output window and continues with the rest.
- Only the "Purge All Revisions" tool (Cleanup panel) is included in this
  package. Other tools from the full YSU Tools extension are not part of
  this download.

Uninstall:
Delete the installed "YSU Tools.extension" folder from your pyRevit
extensions directory and reload pyRevit.
