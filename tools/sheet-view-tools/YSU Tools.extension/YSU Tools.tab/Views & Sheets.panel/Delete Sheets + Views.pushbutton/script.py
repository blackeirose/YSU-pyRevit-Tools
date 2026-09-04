# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from Autodesk.Revit.DB import FilteredElementCollector, View, ViewSheet, ViewType
from pyrevit import forms, script

from ysu_sheets import delete_sheets_and_views, element_id_value


TITLE = "Delete Sheets + Views"
uidoc = __revit__.ActiveUIDocument


def stop(message, expanded=None):
    forms.alert(message, title=TITLE, expanded=expanded, warn_icon=True)
    script.exit()


def safe_view_candidates(doc, target_ids):
    seen = set()
    for ui_view in uidoc.GetOpenUIViews():
        candidate = doc.GetElement(ui_view.ViewId)
        if candidate is not None:
            value = element_id_value(candidate.Id)
            if value not in seen and value not in target_ids:
                seen.add(value)
                yield candidate

    blocked_types = set(
        [
            ViewType.Internal,
            ViewType.ProjectBrowser,
            ViewType.SystemBrowser,
            ViewType.Undefined,
        ]
    )
    for candidate in FilteredElementCollector(doc).OfClass(View).ToElements():
        value = element_id_value(candidate.Id)
        if value in seen or value in target_ids:
            continue
        if candidate.IsTemplate or candidate.ViewType in blocked_types:
            continue
        seen.add(value)
        yield candidate


def switch_away_from_target(doc, target_ids):
    active_view = uidoc.ActiveView
    if active_view is None or element_id_value(active_view.Id) not in target_ids:
        return True
    for candidate in safe_view_candidates(doc, target_ids):
        try:
            uidoc.ActiveView = candidate
            return True
        except Exception:
            pass
    return False


def format_items(items, key_prefix, key_name, limit=25):
    lines = []
    for item in items[:limit]:
        prefix = item.get(key_prefix, "")
        name = item.get(key_name, "")
        lines.append("- {0} - {1}".format(prefix, name))
    if len(items) > limit:
        lines.append("- ... and {0} more".format(len(items) - limit))
    return lines


if uidoc is None:
    stop("No active Revit document is open.")

doc = uidoc.Document
if doc.IsReadOnly:
    stop("The active Revit document is read-only. Sheets cannot be deleted.")

selected_sheets = []
for selected_id in uidoc.Selection.GetElementIds():
    element = doc.GetElement(selected_id)
    if isinstance(element, ViewSheet):
        selected_sheets.append(element)

if not selected_sheets:
    stop(
        "No sheets are selected.\n\n"
        "Select one or more sheets in the Project Browser, then run this command again."
    )

arguments = {
    "sheet_unique_ids": [sheet.UniqueId for sheet in selected_sheets],
    "dry_run": True,
    "confirm": False,
}

try:
    preview = delete_sheets_and_views(doc, arguments)
except Exception as exc:
    stop("Unable to generate the deletion preview.", expanded="{0}".format(exc))

sheet_lines = format_items(preview["sheets"], "sheet_number", "name")
view_lines = format_items(preview["views_to_delete"], "view_type", "name")
shared_lines = format_items(preview["shared_views_retained"], "view_type", "name")

details = []
details.append("SHEETS TO DELETE ({0})".format(len(preview["sheets"])))
details.extend(sheet_lines)
details.append("")
details.append("VIEWS TO DELETE ({0})".format(len(preview["views_to_delete"])))
details.extend(view_lines or ["- None"])
details.append("")
details.append("SHARED VIEWS RETAINED ({0})".format(len(preview["shared_views_retained"])))
details.extend(shared_lines or ["- None"])

confirmed = forms.alert(
    "This will permanently delete {0} sheet(s) and {1} view(s) placed only on those sheets.\n\n"
    "Legends and schedules that are also placed on other sheets will be retained.\n\n"
    "Revit Undo may not be available. Verify your backup and worksharing status before continuing."
    "\n\nDo you want to continue?".format(
        len(preview["sheets"]), len(preview["views_to_delete"])
    ),
    title=TITLE,
    expanded="\n".join(details),
    ok=False,
    yes=True,
    no=True,
    warn_icon=True,
)
if not confirmed:
    script.exit()

target_ids = set(item["element_id"] for item in preview["sheets"])
target_ids.update(item["element_id"] for item in preview["views_to_delete"])
if not switch_away_from_target(doc, target_ids):
    stop(
        "The active sheet or view is included in the deletion, but Revit could not switch "
        "to another safe view.\n\nOpen a view that will not be deleted, then run this command again."
    )

arguments["dry_run"] = False
arguments["confirm"] = True
try:
    result = delete_sheets_and_views(doc, arguments)
except Exception as exc:
    stop(
        "Deletion failed. The Revit transaction was rolled back, so no partial deletion was retained.",
        expanded="{0}".format(exc),
    )

forms.alert(
    "Deletion completed.\n\nSheets deleted: {0}\nViews deleted: {1}\n"
    "Shared views retained: {2}\n\nVerify the Project Browser before saving or synchronizing the model."
    .format(
        len(result["sheets"]),
        len(result["views_to_delete"]),
        len(result["shared_views_retained"]),
    ),
    title=TITLE,
    warn_icon=False,
)
