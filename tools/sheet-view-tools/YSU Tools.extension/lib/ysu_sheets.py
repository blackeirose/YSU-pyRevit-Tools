# -*- coding: utf-8 -*-
"""YSU Tools - Sheet and View utilities."""
from __future__ import unicode_literals

import codecs
import json
import os

from Autodesk.Revit.DB import (
    BuiltInCategory,
    ElementId,
    FilteredElementCollector,
    ScheduleSheetInstance,
    Transaction,
    ViewSheet,
    Viewport,
)
from System import Int32, Int64


def _doc_identity(doc):
    return doc.PathName or doc.Title


def element_id_value(element_id):
    """Return a stable Python integer for Revit 2020-2026 ElementId values."""
    try:
        return int(element_id.Value)
    except Exception:
        return int(element_id.IntegerValue)


def element_id_from_value(value):
    """Create an unambiguous ElementId across Revit's 32/64-bit API versions."""
    try:
        return ElementId(Int64(value))
    except Exception:
        return ElementId(Int32(value))


def _check_document(doc, arguments):
    expected = arguments.get("document_path")
    if expected:
        actual = _doc_identity(doc)
        if os.path.normcase(os.path.normpath(expected)) != os.path.normcase(os.path.normpath(actual)):
            raise ValueError("Active document mismatch. Expected '{0}', active is '{1}'.".format(expected, actual))


def _all_sheets(doc):
    return list(FilteredElementCollector(doc).OfClass(ViewSheet).ToElements())


def _sheet_data(sheet):
    return {
        "element_id": element_id_value(sheet.Id),
        "unique_id": sheet.UniqueId,
        "sheet_number": sheet.SheetNumber,
        "name": sheet.Name,
        "is_placeholder": bool(sheet.IsPlaceholder),
    }


def _view_data(view):
    return {
        "element_id": element_id_value(view.Id),
        "unique_id": view.UniqueId,
        "name": view.Name,
        "view_type": str(view.ViewType),
    }


def _placed_view_ids(doc, sheet_ids):
    result = set()
    viewports = FilteredElementCollector(doc).OfClass(Viewport).ToElements()
    for viewport in viewports:
        if element_id_value(viewport.SheetId) in sheet_ids:
            result.add(element_id_value(viewport.ViewId))
    schedules = FilteredElementCollector(doc).OfClass(ScheduleSheetInstance).ToElements()
    for instance in schedules:
        if element_id_value(instance.OwnerViewId) in sheet_ids and not instance.IsTitleblockRevisionSchedule:
            result.add(element_id_value(instance.ScheduleId))
    return result


def _views_used_on_unselected_sheets(doc, candidate_ids, selected_sheet_ids):
    shared = set()
    for viewport in FilteredElementCollector(doc).OfClass(Viewport).ToElements():
        vid = element_id_value(viewport.ViewId)
        if vid in candidate_ids and element_id_value(viewport.SheetId) not in selected_sheet_ids:
            shared.add(vid)
    for instance in FilteredElementCollector(doc).OfClass(ScheduleSheetInstance).ToElements():
        vid = element_id_value(instance.ScheduleId)
        if vid in candidate_ids and element_id_value(instance.OwnerViewId) not in selected_sheet_ids:
            shared.add(vid)
    return shared


def _resolve_sheets(doc, arguments):
    unique_ids = set(arguments.get("sheet_unique_ids") or [])
    numbers = set(arguments.get("sheet_numbers") or [])
    if not unique_ids and not numbers:
        raise ValueError("Provide at least one sheet_unique_ids or sheet_numbers value.")
    matches = []
    for sheet in _all_sheets(doc):
        if sheet.UniqueId in unique_ids or sheet.SheetNumber in numbers:
            matches.append(sheet)
    matched_uids = set(s.UniqueId for s in matches)
    matched_numbers = set(s.SheetNumber for s in matches)
    missing_uids = sorted(unique_ids - matched_uids)
    missing_numbers = sorted(numbers - matched_numbers)
    if missing_uids or missing_numbers:
        raise ValueError(
            "Sheets not found. unique_ids={0}; sheet_numbers={1}".format(missing_uids, missing_numbers)
        )
    return matches


def list_sheets(doc, arguments):
    _check_document(doc, arguments)
    sheets = sorted(_all_sheets(doc), key=lambda s: (s.SheetNumber, s.Name))
    return {"ok": True, "document": _doc_identity(doc), "sheets": [_sheet_data(s) for s in sheets]}


def delete_sheets_and_views(doc, arguments):
    _check_document(doc, arguments)
    sheets = _resolve_sheets(doc, arguments)
    selected_sheet_ids = set(element_id_value(s.Id) for s in sheets)
    candidate_ids = _placed_view_ids(doc, selected_sheet_ids)
    shared_ids = _views_used_on_unselected_sheets(doc, candidate_ids, selected_sheet_ids)
    deletable_ids = sorted(candidate_ids - shared_ids)
    views = [doc.GetElement(element_id_from_value(vid)) for vid in deletable_ids]
    views = [view for view in views if view is not None]
    shared_views = [doc.GetElement(element_id_from_value(vid)) for vid in sorted(shared_ids)]
    shared_views = [view for view in shared_views if view is not None]

    preview = {
        "ok": True,
        "document": _doc_identity(doc),
        "dry_run": bool(arguments.get("dry_run", True)),
        "sheets": [_sheet_data(s) for s in sheets],
        "views_to_delete": [_view_data(v) for v in views],
        "shared_views_retained": [_view_data(v) for v in shared_views],
    }
    if arguments.get("dry_run", True):
        return preview
    if arguments.get("confirm") is not True:
        raise ValueError("Destructive execution requires confirm=true.")

    transaction = Transaction(doc, "YSU: Delete sheets and placed views")
    transaction.Start()
    try:
        view_ids = [view.Id for view in views]
        for sheet in sheets:
            doc.Delete(sheet.Id)
        for view_id in view_ids:
            if doc.GetElement(view_id) is not None:
                doc.Delete(view_id)
        transaction.Commit()
    except Exception:
        if transaction.HasStarted():
            transaction.RollBack()
        raise
    preview["dry_run"] = False
    preview["deleted"] = True
    return preview
