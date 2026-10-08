# -*- coding: utf-8 -*-
"""Revit 2026 / IronPython ID interop; no numeric round-trip for existing IDs."""
import clr
from System import Enum, Int32, Int64
from pyrevit import DB

try:
    INTEGER_TYPES = (int, long, Int32, Int64)
except NameError:
    INTEGER_TYPES = (int, Int32, Int64)


def as_element_id(value):
    if isinstance(value, DB.ElementId):
        return value
    # Preserve enum overload semantics. Never treat unrelated enums as numeric IDs.
    if isinstance(value, (DB.BuiltInCategory, DB.BuiltInParameter)):
        return DB.ElementId(value)
    if isinstance(value, (bool, Enum)) or not isinstance(value, INTEGER_TYPES):
        raise TypeError('Expected ElementId, BuiltInCategory, BuiltInParameter or an integer ID.')
    return DB.ElementId(Int64(value))  # checked conversion; no 32-bit truncation


def id_value(value):
    # This bundle targets 2026: Value is Int64; IntegerValue is not used/fallbacked.
    if not isinstance(value, DB.ElementId):
        raise TypeError('Expected an existing ElementId for Value access.')
    return int(value.Value)  # IronPython promotes values outside Int32 to Python long


def describe_id(value):
    """Keep diagnostics side-effect free; record original input, never infer it from owner ID."""
    try:
        clr_name = clr.GetClrType(type(value)).FullName
    except Exception:
        clr_name = '<unavailable>'
    numeric = id_value(value) if isinstance(value, DB.ElementId) else repr(value)
    return 'value={0}; Python={1}; CLR={2}'.format(numeric, type(value).__name__, clr_name)
