# -*- coding: utf-8 -*-
"""Read displayed schedule cells only. No Transaction or model writes."""
from __future__ import unicode_literals
from pyrevit import DB
from handoff import make_payload


def element_id_value(element_id):
    # Revit 2024+ exposes a 64-bit Value; older Revit uses IntegerValue.
    return int(element_id.Value if hasattr(element_id, 'Value') else element_id.IntegerValue)


def available_schedules(doc):
    schedules = [view for view in DB.FilteredElementCollector(doc).OfClass(DB.ViewSchedule)
                 if not view.IsTemplate and not view.IsInternalKeynoteSchedule
                 and not view.IsTitleblockRevisionSchedule]
    return sorted(schedules, key=lambda view: (view.Name.lower(), element_id_value(view.Id)))


def read_schedule(doc, schedule):
    table = schedule.GetTableData()
    body = table.GetSectionData(DB.SectionType.Body)
    if body.NumberOfRows == 0 or body.NumberOfColumns == 0:
        raise ValueError('The selected schedule has no displayed table data.')
    if body.NumberOfRows > 500 or body.NumberOfColumns > 64:
        raise ValueError('This schedule exceeds the V1 table limit. No rows were truncated.')
    definition = schedule.Definition
    fields = [definition.GetField(fid) for fid in definition.GetFieldOrder()]
    visible = [field for field in fields if not field.IsHidden]
    if len(visible) != body.NumberOfColumns:
        raise ValueError('This table structure cannot be matched reliably to displayed fields. Use the Web PDF/Image workflow.')
    columns = [field.ColumnHeading or field.GetName() for field in visible]
    rows = [[schedule.GetCellText(DB.SectionType.Body, r, c)
             for c in range(body.FirstColumnNumber, body.LastColumnNumber + 1)]
            for r in range(body.FirstRowNumber, body.LastRowNumber + 1)]
    # Keep body headings, blanks, subtotal/grand-total rows. The user reviews them.
    return make_payload(doc.Title, schedule.Name, element_id_value(schedule.Id), columns, rows)
