PICK FACE MATERIAL
Version: 1.0.0

Purpose:
Lets you pick a face in the active Revit model and immediately identify
its material. If the face has a Paint override, that painted material is
used; otherwise the face's base material is used. The material's exact
name is copied to the Windows clipboard, and Revit's Materials browser is
opened automatically so you can paste the name into its search box. The
tool never modifies the model.

Usage:
1. Click "Pick Face Material" on the YSU Tools tab (Materials panel).
2. Pick a face in the active model when prompted.
3. The material name is copied to the clipboard and the Materials
   browser opens.
4. Press Esc while picking to cancel with no action.

Installation:
1. Download the ZIP.
2. Extract it. You will get a folder named "YSU Tools.extension".
3. Copy the "YSU Tools.extension" folder into the pyRevit extensions
   folder configured for your installation (use pyRevit > Settings to
   find or add an extensions search path if you are not sure where
   that is).
4. Reload pyRevit (pyRevit tab > Reload) or restart Revit.
5. Confirm the "YSU Tools" tab appears with a "Materials" panel
   containing the "Pick Face Material" button.

Supported Revit version(s):
Revit 2019 and later (standard pyRevit-supported Revit API, no
version-specific calls).

Supported pyRevit version(s):
pyRevit 4.8 and later (CPython3 or IronPython engine).

Notes / limitations:
- Faces belonging to linked Revit models are not supported in this
  version; pick a face in the active (host) model.
- If a face uses category/default graphics with no assigned material,
  or geometry the tool cannot resolve, no material can be identified.
- Only the "Pick Face Material" tool (Materials panel) is included in
  this package. Other tools from the full YSU Tools extension are not
  part of this download.

Uninstall:
Delete the installed "YSU Tools.extension" folder from your pyRevit
extensions directory and reload pyRevit.
