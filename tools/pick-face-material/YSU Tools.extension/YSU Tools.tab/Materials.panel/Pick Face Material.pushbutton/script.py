# -*- coding: utf-8 -*-
"""Pick the material assigned to a Revit face.

Workflow:
1. Click this tool.
2. Pick a face in the active Revit model.
3. If the face has been Painted, use the painted material.
4. Otherwise, use the face's base material.
5. Copy the material name to the Windows clipboard.
6. Open Revit's Materials browser.

The tool does not modify the model.
"""

__title__ = "Pick Face\nMaterial"
__author__ = "YSU"
__doc__ = (
    "Pick a model face, copy its actual material name to the clipboard, "
    "and open Revit Materials. Painted material is prioritized."
)

from pyrevit import DB, UI, HOST_APP, forms, revit, script
from Autodesk.Revit.Exceptions import OperationCanceledException


doc = revit.doc
uidoc = revit.uidoc


def pick_face():
    """Ask the user to pick a face and return (element, face)."""
    reference = uidoc.Selection.PickObject(
        UI.Selection.ObjectType.Face,
        "Pick a face to identify its material"
    )

    element = doc.GetElement(reference.ElementId)

    # v1 intentionally supports faces in the active model only.
    if isinstance(element, DB.RevitLinkInstance):
        forms.alert(
            "Linked-model faces are not supported in this version.\n\n"
            "Please pick a face in the active Revit model.",
            title="Pick Face Material",
            warn_icon=True
        )
        script.exit()

    face = element.GetGeometryObjectFromReference(reference)

    if face is None or not isinstance(face, DB.Face):
        raise Exception("The selected reference could not be resolved to a Revit Face.")

    return element, face


def resolve_face_material(element, face):
    """Return (Material, source_label), prioritizing Paint overrides."""
    # 1) Painted material override
    try:
        if doc.IsPainted(element.Id, face):
            material_id = doc.GetPaintedMaterial(element.Id, face)
            if material_id and material_id != DB.ElementId.InvalidElementId:
                material = doc.GetElement(material_id)
                if isinstance(material, DB.Material):
                    return material, "Paint"
    except Exception:
        # Some unusual geometry/reference types may not support the paint query.
        # Continue to the face's base material.
        pass

    # 2) Base material directly assigned to the face geometry
    try:
        material_id = face.MaterialElementId
        if material_id and material_id != DB.ElementId.InvalidElementId:
            material = doc.GetElement(material_id)
            if isinstance(material, DB.Material):
                return material, "Base"
    except Exception:
        pass

    return None, None


def open_materials_browser():
    """Post Revit's built-in Materials command."""
    command_id = UI.RevitCommandId.LookupPostableCommandId(
        UI.PostableCommand.Materials
    )
    HOST_APP.uiapp.PostCommand(command_id)


def main():
    try:
        element, face = pick_face()
    except OperationCanceledException:
        # ESC = clean exit, no warning.
        return
    except Exception as exc:
        forms.alert(
            "Could not read the selected face.\n\n{}".format(exc),
            title="Pick Face Material",
            warn_icon=True
        )
        return

    material, source = resolve_face_material(element, face)

    if material is None:
        forms.alert(
            "No material could be resolved from this face.\n\n"
            "The face may use category/default graphics or unsupported geometry.",
            title="Pick Face Material",
            warn_icon=True
        )
        return

    # Put the exact Revit material name on the clipboard so the user can
    # paste it directly into the Materials browser search box.
    try:
        script.clipboard_copy(material.Name)
    except Exception as exc:
        forms.alert(
            "Material found: {}\n\n"
            "But its name could not be copied to the clipboard.\n\n{}".format(
                material.Name, exc
            ),
            title="Pick Face Material",
            warn_icon=True
        )

    # Open Materials after the current pyRevit API context completes.
    try:
        open_materials_browser()
    except Exception as exc:
        forms.alert(
            "Material found: {}\n"
            "Source: {}\n\n"
            "The material name has been copied to the clipboard, "
            "but Revit's Materials browser could not be opened automatically.\n\n"
            "{}".format(material.Name, source, exc),
            title="Pick Face Material",
            warn_icon=True
        )


if __name__ == "__main__":
    main()
