# -*- coding: utf-8 -*-
"""Revit 2026 adapter. No model/material writes, Save, Sync, or ownership checkout."""
import json
import math
import uuid
import traceback

from System import Guid, String
from System.Collections.Generic import List
from pyrevit import DB
from Autodesk.Revit.DB.ExtensibleStorage import Schema, SchemaBuilder, Entity, AccessLevel, DataStorage
from legend_core import (OWNER, DEFAULT_LAYOUT, LegendError, OperationState, atomic, delta,
                         material_rows, stamp, validate_registry, validate_row,
                         validate_stamp, ScanIssues, CATEGORY_KEYS, CATEGORY_LABELS,
                         CATEGORY_RULES, DEFAULT_CATEGORIES, validate_categories,
                         legend_settings, with_settings, legend_rows, new_rows)
from legend_ids import as_element_id, id_value, describe_id
from legend_dependencies import check_dependencies

diagnostics = OperationState()

SCHEMA_GUID = Guid('46d825be-9a7c-482d-9d84-2ee5b2ce58b3')
INVALID = DB.ElementId.InvalidElementId
MM = 1.0 / 304.8
VOLUME_EPS = 1e-9  # cubic feet; Revit numerical tolerance, not a bounding-box test


def eid(value):
    return id_value(value)


def material_from_id(doc, material_id):
    diagnostics.phase('Scan / Material lookup', diagnostics.element)
    diagnostics.id_input = describe_id(material_id)
    return doc.GetElement(as_element_id(material_id))


def element_name(element):
    return DB.Element.Name.GetValue(element)


def schema(create=False):
    result = Schema.Lookup(SCHEMA_GUID)
    if result is None and create:
        builder = SchemaBuilder(SCHEMA_GUID)
        builder.SetSchemaName('YSUColorLegendV1')
        builder.SetReadAccessLevel(AccessLevel.Public)
        builder.SetWriteAccessLevel(AccessLevel.Public)
        builder.AddSimpleField('Payload', String)
        result = builder.Finish()
    if result is not None and (result.SchemaName != 'YSUColorLegendV1' or result.GetField('Payload') is None):
        raise LegendError('Extensible Storage schema collision.')
    return result


def read_data(element):
    sc = schema()
    if sc is None:
        return None
    entity = element.GetEntity(sc)
    if not entity.IsValid():
        return None
    try:
        return json.loads(entity.Get[String](sc.GetField('Payload')))
    except Exception as exc:
        error = LegendError('Invalid tool metadata on element {0}: {1}'.format(eid(element.Id), exc))
        error.original_traceback = traceback.format_exc()
        raise error


def write_data(element, data):
    sc = schema(True)
    entity = Entity(sc)
    entity.Set[String](sc.GetField('Payload'), json.dumps(data, ensure_ascii=True, sort_keys=True))
    element.SetEntity(entity)


def editable(doc, element):
    if element.Pinned or element.GroupId != INVALID:
        raise LegendError('Pinned/grouped tool element {0}; preserved.'.format(eid(element.Id)))
    if doc.IsWorkshared and DB.WorksharingUtils.GetCheckoutStatus(doc, element.Id) == DB.CheckoutStatus.OwnedByOtherUser:
        raise LegendError('Element {0} is owned by another user; preserved.'.format(eid(element.Id)))


class AbortFailures(DB.IFailuresPreprocessor):
    def __init__(self):
        self.messages = []

    def PreprocessFailures(self, accessor):
        failures = list(accessor.GetFailureMessages())
        if failures:
            self.messages.extend(f.GetDescriptionText() for f in failures)
            return DB.FailureProcessingResult.ProceedWithRollBack
        return DB.FailureProcessingResult.Continue


class AtomicTransaction(object):
    def __init__(self, doc, title):
        self.doc = doc
        self.group = DB.TransactionGroup(doc, title)
        self.tx = DB.Transaction(doc, title)
        self.failures = AbortFailures()

    def start(self):
        diagnostics.transaction = 'rollback_unconfirmed'
        try:
            if self.group.Start() != DB.TransactionStatus.Started:
                raise LegendError('Cannot start legend transaction group.')
            if self.tx.Start() != DB.TransactionStatus.Started:
                raise LegendError('Cannot start legend transaction.')
            diagnostics.transaction = 'started'
            options = self.tx.GetFailureHandlingOptions()
            options.SetFailuresPreprocessor(self.failures)
            options.SetClearAfterRollback(True)
            options.SetForcedModalHandling(True)
            self.tx.SetFailureHandlingOptions(options)
        except Exception:
            original = traceback.format_exc()
            try:
                self.rollback()
            except Exception as rollback_error:
                rollback_error.original_traceback = original
                raise
            raise

    def commit(self):
        diagnostics.phase('Write / Regenerate before commit')
        self.doc.Regenerate()
        diagnostics.phase('Write / Commit transaction')
        if self.tx.Commit() != DB.TransactionStatus.Committed:
            raise LegendError('Revit rejected update: ' + '; '.join(self.failures.messages))
        diagnostics.phase('Write / Assimilate transaction group')
        if self.group.Assimilate() != DB.TransactionStatus.Committed:
            raise LegendError('Could not assimilate legend update.')
        diagnostics.transaction = 'committed'

    def rollback(self):
        try:
            status = DB.TransactionStatus
            if self.tx.GetStatus() == status.Started:
                if self.tx.RollBack() != DB.TransactionStatus.RolledBack:
                    raise LegendError('Transaction rollback did not complete.')
            tx_status = self.tx.GetStatus()
            if tx_status not in (status.Uninitialized, status.RolledBack, status.Committed):
                raise LegendError('Unexpected transaction state: ' + str(tx_status))
            if self.group.GetStatus() == status.Started:
                if self.group.RollBack() != DB.TransactionStatus.RolledBack:
                    raise LegendError('TransactionGroup rollback did not complete.')
            group_status = self.group.GetStatus()
            if group_status == status.RolledBack:
                diagnostics.transaction = 'rolled_back'
            elif group_status == status.Uninitialized and tx_status == status.Uninitialized:
                diagnostics.transaction = 'not_started'
            else:
                raise LegendError('Unexpected transaction group state: ' + str(group_status))
        except Exception as exc:
            diagnostics.transaction = 'rollback_unconfirmed'
            raise LegendError('ROLLBACK UNCONFIRMED. Stop and inspect Undo/document state: ' + str(exc))


def supported_plan(view):
    return isinstance(view, DB.ViewPlan) and not view.IsTemplate and view.ViewType == DB.ViewType.FloorPlan


def plane_elevation(doc, view, vrange, plane):
    level_id = vrange.GetLevelId(plane)
    if level_id == DB.PlanViewRange.Unlimited:
        raise LegendError('Unlimited View Range is not supported in v1; use finite levels.')
    if level_id == DB.PlanViewRange.Current:
        level = view.GenLevel
    elif level_id in (DB.PlanViewRange.LevelAbove, DB.PlanViewRange.LevelBelow):
        raise LegendError('Unresolved relative View Range level; use an explicit Level in v1.')
    else:
        level = doc.GetElement(level_id)
    if not isinstance(level, DB.Level):
        raise LegendError('Cannot resolve View Range level.')
    return level.ProjectElevation + vrange.GetOffset(plane)


def scope_for_view(doc, view):
    if not supported_plan(view):
        raise LegendError('Use a Floor Plan (not Family Editor, ceiling/structural/area plan or Legend View).')
    if view.GetPrimaryViewId() != INVALID or list(view.GetDependentViewIds()):
        raise LegendError('Dependent views and their primary view are not supported in v1 (annotation isolation).')
    if abs(view.ViewDirection.Z) < 0.999999:
        raise LegendError('Only horizontal floor plans are supported.')
    if view.GetUnderlayBaseLevel() != INVALID:
        raise LegendError('Underlay is enabled; v1 cannot resolve its separate visibility range.')
    if view.IsTemporaryHideIsolateActive() or view.IsInTemporaryViewMode(DB.TemporaryViewMode.TemporaryViewProperties):
        raise LegendError('Exit Temporary Hide/Isolate or Temporary View Properties before updating.')
    # Plan Regions no longer block (user decision 0.1.4): their local ranges are ignored and
    # the main View Range + Crop below decide every solid. See plan_region_ids/scan.
    vrange = view.GetViewRange()
    bottom = plane_elevation(doc, view, vrange, DB.PlanViewPlane.BottomClipPlane)
    depth = plane_elevation(doc, view, vrange, DB.PlanViewPlane.ViewDepthPlane)
    top = plane_elevation(doc, view, vrange, DB.PlanViewPlane.TopClipPlane)
    cut = plane_elevation(doc, view, vrange, DB.PlanViewPlane.CutPlane)
    vrange.Dispose()
    if not depth <= bottom <= cut <= top or top - depth <= 1e-6:
        raise LegendError('Unsupported or degenerate floor-plan View Range.')
    crop_solid = None
    if view.CropBoxActive:
        manager = view.GetCropRegionShapeManager()
        if manager.Split or manager.NumberOfSplitRegions > 1:
            raise LegendError('Split Crop is not supported in v1.')
        loops = list(manager.GetCropShape())
        if len(loops) != 1:
            raise LegendError('Multiple Crop loops are not supported in v1.')
        loop = loops[0]
        # Ordinary rectangle or a single simple straight-edged polygon, including concave crop.
        if any(not isinstance(curve, DB.Line) for curve in loop):
            raise LegendError('Non-linear Crop boundary is not supported in v1.')
        origin_z = list(loop)[0].GetEndPoint(0).Z
        shifted = DB.CurveLoop.CreateViaTransform(loop, DB.Transform.CreateTranslation(DB.XYZ(0, 0, depth - origin_z)))
        crop_solid = DB.GeometryCreationUtilities.CreateExtrusionGeometry(
            List[DB.CurveLoop]([shifted]), DB.XYZ.BasisZ, top - depth)
        manager.Dispose()
    return depth, top, crop_solid


def geometry_hidden(doc, view, geometry):
    style_id = geometry.GraphicsStyleId
    if style_id != INVALID:
        style = doc.GetElement(style_id)
        if style is not None and style.GraphicsStyleCategory is not None:
            category = style.GraphicsStyleCategory
            if view.CanCategoryBeHidden(category.Id) and view.GetCategoryHidden(category.Id):
                return True
    return False


def walk_solids(doc, view, geometry, transform, inherited=None, depth=0):
    if geometry is None:
        raise LegendError('Casework geometry read returned null.')
    if depth > 32:
        raise LegendError('GeometryInstance nesting exceeds 32 levels.')
    own_material = geometry.MaterialElement
    inherited = own_material.Id if own_material is not None else inherited
    for obj in geometry:
        if geometry_hidden(doc, view, obj):
            continue
        if isinstance(obj, DB.GeometryInstance):
            nested = obj.GetSymbolGeometry()
            for solid, trans, material in walk_solids(doc, view, nested, transform.Multiply(obj.Transform), inherited, depth + 1):
                yield solid, trans, material
        elif isinstance(obj, DB.Solid):
            if obj.Faces.Size and obj.Volume > VOLUME_EPS:
                yield obj, transform, inherited
            elif obj.Faces.Size:
                raise LegendError('Open/zero-volume solid is not supported; existing legend preserved.')
        elif isinstance(obj, DB.Mesh):
            raise LegendError('Mesh Casework geometry is not supported; existing legend preserved.')
        elif isinstance(obj, (DB.Curve, DB.PolyLine, DB.Point)):
            continue  # symbolic/model linework has no department solid volume
        else:
            raise LegendError('Unsupported geometry type: ' + obj.GetType().Name)


def clip_solid(solid, scope):
    bottom, top, crop = scope
    if crop is not None:
        return DB.BooleanOperationsUtils.ExecuteBooleanOperation(solid, crop, DB.BooleanOperationsType.Intersect)
    lower = DB.Plane.CreateByNormalAndOrigin(DB.XYZ.BasisZ, DB.XYZ(0, 0, bottom))
    upper = DB.Plane.CreateByNormalAndOrigin(DB.XYZ(0, 0, -1), DB.XYZ(0, 0, top))
    result = DB.BooleanOperationsUtils.CutWithHalfSpace(solid, lower)
    if result.Volume <= VOLUME_EPS:
        return result
    return DB.BooleanOperationsUtils.CutWithHalfSpace(result, upper)


def element_materials(doc, view, element, options, scope, fallback_options=None):
    """Materials of this element's connected volumes that intersect the main View Range/Crop.

    Returns ({Material.UniqueId: Material}, solids, in_scope, used_fallback).
    """
    found = {}
    solids = in_scope = 0
    geometry = element.get_Geometry(options)
    used_fallback = geometry is None and fallback_options is not None
    if used_fallback:
        geometry = element.get_Geometry(fallback_options)
    for solid, trans, inherited in walk_solids(doc, view, geometry, DB.Transform.Identity):
        # Split disconnected volumes before clipping so an in-range volume cannot
        # qualify material on a separate out-of-range volume of the same solid.
        for volume in DB.SolidUtils.SplitVolumes(solid):
            solids += 1
            world = DB.SolidUtils.CreateTransformed(volume, trans)
            clipped = clip_solid(world, scope)
            if clipped.Volume <= VOLUME_EPS:
                continue
            in_scope += 1
            ids = {}
            for face in volume.Faces:
                material_id = face.MaterialElementId
                if material_id == INVALID:
                    material_id = inherited
                if material_id is None or material_id == INVALID:
                    raise LegendError('In-range solid has an unresolved face material.')
                ids[eid(material_id)] = material_id  # retain the original DB.ElementId
            # A single department material per connected volume is exact even
            # when every original surface is outside the clipping volume.
            # Multiple face materials require surface attribution after clipping;
            # do not silently include materials from out-of-range faces.
            if len(ids) != 1:
                raise LegendError('One connected solid has multiple face materials; '
                                  'v1 supports one assigned material per connected department solid.')
            material = material_from_id(doc, next(iter(ids.values())))
            if not isinstance(material, DB.Material):
                raise LegendError('Face material does not resolve to a local Material.')
            found[material.UniqueId] = material
    if not solids and list(element.GetMaterialIds(False)):
        raise LegendError('Material candidates exist but no readable solid was returned.')
    return found, solids, in_scope, used_fallback


def plan_region_ids(doc, view):
    # OwnerViewId rather than view-scoped visibility: a hidden Plan Region still changes range.
    return [eid(region.Id) for region in
            DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_PlanRegion).WhereElementIsNotElementType()
            if region.OwnerViewId == view.Id]


def plan_region_candidates(doc, view, scope, seen, category=None):
    """Elements the view-scoped collector may omit because a Plan Region's local range hides them.

    The bounding box is only a coarse prefilter on the MAIN range/Crop; exact per-solid
    clipping in element_materials decides inclusion.
    """
    bottom, top, crop = scope
    far = 1.0e6  # feet; no Crop means no horizontal limit
    low, high = [-far, -far], [far, far]
    if crop is not None:
        box = crop.GetBoundingBox()
        corners = [box.Transform.OfPoint(DB.XYZ(x, y, box.Min.Z))
                   for x in (box.Min.X, box.Max.X) for y in (box.Min.Y, box.Max.Y)]
        low = [min(p.X for p in corners), min(p.Y for p in corners)]
        high = [max(p.X for p in corners), max(p.Y for p in corners)]
    outline = DB.Outline(DB.XYZ(low[0], low[1], bottom), DB.XYZ(high[0], high[1], top))
    category = DB.BuiltInCategory.OST_Casework if category is None else category
    collector = (DB.FilteredElementCollector(doc).OfCategory(category)
                 .WhereElementIsNotElementType().WherePasses(DB.BoundingBoxIntersectsFilter(outline)))
    return [element for element in collector if eid(element.Id) not in seen]


def controlling_view(doc, view, parameter_name):
    """The View Template's setting applies when the template controls this parameter."""
    if view.ViewTemplateId == INVALID:
        return view
    template = doc.GetElement(view.ViewTemplateId)
    if template is None:
        raise LegendError('View Template {0} cannot be read.'.format(eid(view.ViewTemplateId)))
    parameter = eid(as_element_id(getattr(DB.BuiltInParameter, parameter_name)))
    free = set(eid(i) for i in template.GetNonControlledTemplateParameterIds())
    return view if parameter in free else template


def hidden_reason(doc, view, element, label=None):
    """Why the view hides this element by explicit, API-readable rules; None when displayed.

    Used only for elements outside the view-scoped collector when Plan Regions exist, so view
    hiding is not bypassed. A rule that cannot be evaluated reliably stops the scan.
    """
    label = label or 'Casework [ID {0}]'.format(eid(element.Id))
    if element.IsHidden(view):
        return 'hidden in view'
    category = element.Category
    if category is None:
        raise LegendError(label + ' has no category; its visibility cannot be evaluated.')
    graphics = controlling_view(doc, view, 'VIS_GRAPHICS_MODEL')
    if graphics.AreModelCategoriesHidden or graphics.GetCategoryHidden(category.Id):
        return 'model category hidden'
    option = element.DesignOption
    if option is not None:
        raise LegendError(u'{0} is in Design Option "{1}" outside the view collector; its visibility '
                          u'with Plan Regions cannot be evaluated reliably. Existing legend preserved.'.format(
                              label, element_name(option)))
    filters = controlling_view(doc, view, 'VIS_GRAPHICS_FILTERS')
    for filter_id in filters.GetFilters():
        if not filters.GetIsFilterEnabled(filter_id) or filters.GetFilterVisibility(filter_id):
            continue
        rule = doc.GetElement(filter_id)
        if isinstance(rule, DB.ParameterFilterElement):
            if eid(category.Id) in set(eid(i) for i in rule.GetCategories()):
                element_filter = rule.GetElementFilter()
                if element_filter is None or element_filter.PassesFilter(element):
                    return u'hidden by view filter ' + element_name(rule)
        elif isinstance(rule, DB.SelectionFilterElement):
            if eid(element.Id) in set(eid(i) for i in rule.GetElementIds()):
                return u'hidden by selection filter ' + element_name(rule)
        else:
            raise LegendError('{0}: view filter {1} has an unsupported type; visibility cannot be '
                              'evaluated.'.format(label, eid(filter_id)))
    phase = view.get_Parameter(DB.BuiltInParameter.VIEW_PHASE)
    phase_filter = controlling_view(doc, view, 'VIEW_PHASE_FILTER').get_Parameter(
        DB.BuiltInParameter.VIEW_PHASE_FILTER)
    if phase is None or phase_filter is None:
        raise LegendError(label + ': view Phase / Phase Filter cannot be read.')
    status = element.GetPhaseStatus(phase.AsElementId())
    if status in (DB.ElementOnPhaseStatus.Future, DB.ElementOnPhaseStatus.Past):
        return 'phase status {0}'.format(status)
    if status == getattr(DB.ElementOnPhaseStatus, 'None'):
        raise LegendError(label + ': phase status is undefined; visibility cannot be evaluated.')
    phase_filter_element = doc.GetElement(phase_filter.AsElementId())
    if phase_filter_element is not None:  # no Phase Filter shows every phase status
        if phase_filter_element.GetPhaseStatusPresentation(status) == DB.PhaseStatusPresentation.DontShow:
            return u'phase status {0} hidden by phase filter {1}'.format(status, element_name(phase_filter_element))
    if doc.IsWorkshared:
        workset_id = element.WorksetId
        workset = doc.GetWorksetTable().GetWorkset(workset_id)
        if workset is None or not workset.IsOpen:
            return 'workset closed'
        state = controlling_view(doc, view, 'VIS_GRAPHICS_WORKSETS').GetWorksetVisibility(workset_id)
        if state == DB.WorksetVisibility.Hidden:
            return 'workset hidden in view'
        if (state == DB.WorksetVisibility.UseGlobalSetting and not DB.WorksetDefaultVisibilitySettings
                .GetWorksetDefaultVisibilitySettings(doc).IsWorksetVisible(workset_id)):
            return 'workset hidden by default'
    return None


HOST_CLASSES = {'OST_Walls': 'Wall', 'OST_Floors': 'Floor', 'OST_Ceilings': 'Ceiling'}
RULE_TEXT = {'wall_exterior': u'Wall Exterior 側最外層', 'floor_top': u'Floor 最上層',
             'ceiling_bottom': u'Ceiling 最下層'}
SURFACE_TOL = 1.0 / 304.8  # 1 mm probe slab on the outer side of a Floor top / Ceiling bottom face


def compound_layers(doc, element, key):
    """(layers, None) or (None, reason it is unsupported).

    Revit 2026 API: CompoundStructure.GetLayers() is ordered exterior->interior for walls and
    top->bottom for floors/ceilings. Wall.Flipped swaps which physical side is the wall's
    exterior; it does not reorder the type's layers, so layer 0 stays the wall's Exterior.
    """
    host_class = getattr(DB, HOST_CLASSES[key])
    if not isinstance(element, host_class):
        return None, u'{0} is not a system {1} (e.g. Model In-Place) and has no compound layers; unsupported.'.format(
            element.GetType().Name, HOST_CLASSES[key])
    if key == 'OST_Walls':
        kind = element.WallType.Kind
        if kind != DB.WallKind.Basic:
            return None, u'{0} wall has no single exterior compound layer; unsupported.'.format(kind)
        if element.IsStackedWallMember:
            return None, u'Stacked wall member; unsupported.'
    element_type = doc.GetElement(element.GetTypeId())
    type_name = element_name(element_type) if element_type is not None else u'?'
    structure = element_type.GetCompoundStructure() if element_type is not None else None
    if structure is None:
        return None, u'Type "{0}" has no compound structure; unsupported.'.format(type_name)
    if structure.IsVerticallyCompound:
        return None, u'Type "{0}" is vertically compound (no single outer layer); unsupported.'.format(type_name)
    layers = list(structure.GetLayers())
    if not layers:
        return None, u'Type "{0}" has no layers; unsupported.'.format(type_name)
    return layers, None


def surface_layer_material(doc, key, layers):
    """Exactly one layer: wall exterior (0), floor top (0) or ceiling bottom (last). Never a fallback."""
    rule = CATEGORY_RULES[key]
    index = len(layers) - 1 if rule == 'ceiling_bottom' else 0
    layer = layers[index]
    if layer.MaterialId == INVALID:
        raise LegendError(u'{0}（layer {1}/{2}, {3}）has no material (<By Category>); other layers are not used.'.format(
            RULE_TEXT[rule], index + 1, len(layers), layer.Function))
    material = material_from_id(doc, layer.MaterialId)
    if not isinstance(material, DB.Material):
        raise LegendError(u'{0} material does not resolve to a local Material.'.format(RULE_TEXT[rule]))
    return material


def box_in_scope(element, scope):
    """Coarse, inclusive test used only to decide whether an UNSUPPORTED element must be reported."""
    bottom, top, crop = scope
    box = element.get_BoundingBox(None)
    if box is None:
        return True  # cannot rule it out: report rather than silently skip
    pts = [box.Transform.OfPoint(DB.XYZ(x, y, z)) for x in (box.Min.X, box.Max.X)
           for y in (box.Min.Y, box.Max.Y) for z in (box.Min.Z, box.Max.Z)]
    if max(p.Z for p in pts) < bottom - SURFACE_TOL or min(p.Z for p in pts) > top + SURFACE_TOL:
        return False
    if crop is not None:
        cb = crop.GetBoundingBox()
        cpts = [cb.Transform.OfPoint(DB.XYZ(x, y, cb.Min.Z)) for x in (cb.Min.X, cb.Max.X) for y in (cb.Min.Y, cb.Max.Y)]
        if (max(p.X for p in pts) < min(p.X for p in cpts) or min(p.X for p in pts) > max(p.X for p in cpts) or
                max(p.Y for p in pts) < min(p.Y for p in cpts) or min(p.Y for p in pts) > max(p.Y for p in cpts)):
            return False
    return True


def solids_in_scope(doc, view, element, options, scope, fallback_options=None):
    """Wall body: any connected volume inside the main View Range/Crop (same test as Casework)."""
    geometry = element.get_Geometry(options)
    used_fallback = geometry is None and fallback_options is not None
    if used_fallback:
        geometry = element.get_Geometry(fallback_options)
    solids = in_scope = 0
    for solid, trans, _ in walk_solids(doc, view, geometry, DB.Transform.Identity):
        for volume in DB.SolidUtils.SplitVolumes(solid):
            solids += 1
            if clip_solid(DB.SolidUtils.CreateTransformed(volume, trans), scope).Volume > VOLUME_EPS:
                in_scope += 1
    return solids, in_scope, used_fallback


def surface_in_scope(element, key, scope):
    """Floor top / Ceiling bottom faces: a 1 mm slab on the face's outer side is clipped by the
    main range, so a floor whose top sits on View Depth counts and one whose top sits on the
    Top plane (next level's slab) does not. Ceilings mirror this."""
    top = CATEGORY_RULES[key] == 'floor_top'
    side = u'top' if top else u'bottom'
    refs = DB.HostObjectUtils.GetTopFaces(element) if top else DB.HostObjectUtils.GetBottomFaces(element)
    faces = in_scope = 0
    for ref in refs:
        face = element.GetGeometryObjectFromReference(ref)
        if not isinstance(face, DB.PlanarFace):
            raise LegendError(u'{0} face is not planar; unsupported in this version.'.format(side))
        normal = face.FaceNormal
        if (normal.Z <= 0) if top else (normal.Z >= 0):
            raise LegendError(u'{0} face normal is not {1}ward; cannot place the scope probe.'.format(
                side, u'up' if top else u'down'))
        faces += 1
        probe = DB.GeometryCreationUtilities.CreateExtrusionGeometry(face.GetEdgesAsCurveLoops(), normal, SURFACE_TOL)
        if clip_solid(probe, scope).Volume > VOLUME_EPS:
            in_scope += 1
    if not faces:
        raise LegendError(u'Revit returned no {0} face; scope cannot be evaluated.'.format(side))
    return faces, in_scope


def element_scan(doc, view, element, key, options, scope, fallback_options=None):
    """({Material.UniqueId: Material}, solids/faces, in_scope, used_fallback) for one element."""
    if CATEGORY_RULES[key] == 'geometry':
        return element_materials(doc, view, element, options, scope, fallback_options)
    layers, unsupported = compound_layers(doc, element, key)
    if unsupported is not None:
        if box_in_scope(element, scope):
            raise LegendError(unsupported)
        return {}, 0, 0, False
    used_fallback = False
    if key == 'OST_Walls':
        parts, in_scope, used_fallback = solids_in_scope(doc, view, element, options, scope, fallback_options)
    else:
        parts, in_scope = surface_in_scope(element, key, scope)
    if not in_scope:
        return {}, parts, 0, used_fallback
    material = surface_layer_material(doc, key, layers)
    return {material.UniqueId: material}, parts, in_scope, used_fallback


def scan(doc, view, categories=None):
    """Fail closed on ambiguity. FEC is only the first filter; every element is judged by the
    MAIN View Range and Crop (Plan Region local ranges ignored, 0.1.4). Problems are collected
    for all elements and raised together BEFORE any write; they are never an empty result."""
    categories = validate_categories(list(categories or DEFAULT_CATEGORIES))
    diagnostics.source = u'{0} [ID {1}]'.format(view.Name, eid(view.Id))
    diagnostics.phase('Scan / View scope')
    scope = scope_for_view(doc, view)
    regions = plan_region_ids(doc, view)
    options = DB.Options()
    options.View = view
    options.IncludeNonVisibleObjects = False
    options.ComputeReferences = False
    fallback = None
    if regions:
        fallback = DB.Options()
        fallback.DetailLevel = view.DetailLevel
        fallback.IncludeNonVisibleObjects = False
        fallback.ComputeReferences = False
    found = {}  # Material.UniqueId -> [Material, set(category keys)]
    issues = []
    counts = {'elements': 0, 'solids': 0, 'in_scope': 0, 'categories': list(categories),
              'by_category': {}, 'plan_regions': len(regions),
              'plan_region_added': [], 'plan_region_hidden': [], 'detail_geometry': []}

    def record(label, key, exc):
        issue = {'element': label, 'category': key, 'reason': u'{0}'.format(exc) if isinstance(exc, LegendError)
                 else u'{0}: {1}'.format(type(exc).__name__, exc),
                 'stage': diagnostics.stage, 'id_input': diagnostics.id_input}
        if not isinstance(exc, LegendError):
            issue['traceback'] = traceback.format_exc()
        issues.append(issue)

    for key in categories:
        counts['by_category'][key] = 0
        category = getattr(DB.BuiltInCategory, key)
        diagnostics.phase('Scan / View collector', CATEGORY_LABELS[key])
        elements = list(DB.FilteredElementCollector(doc, view.Id).OfCategory(category).WhereElementIsNotElementType())
        candidates = [(element, False) for element in elements]
        if regions:
            # The view collector follows displayed graphics, so a Plan Region range can omit
            # elements that the main range includes. Recheck only those.
            seen = set(eid(element.Id) for element in elements)
            candidates += [(element, True) for element in plan_region_candidates(doc, view, scope, seen, category)]
        for element, recovered in candidates:
            label = u'{0} [ID {1}]'.format(CATEGORY_LABELS[key], eid(element.Id))
            try:
                diagnostics.phase('Scan / Plan Region: element outside view collector' if recovered
                                  else 'Scan / Element geometry and material', label)
                materials, parts, in_scope, used_fallback = element_scan(
                    doc, view, element, key, options, scope, fallback if recovered else None)
                if recovered:
                    if not materials:
                        continue  # outside the main View Range / Crop
                    diagnostics.phase('Scan / Plan Region: view visibility rules', label)
                    reason = hidden_reason(doc, view, element, label)
                    if reason:
                        counts['plan_region_hidden'].append(u'{0}: {1}'.format(eid(element.Id), reason))
                        continue
                    counts['plan_region_added'].append(eid(element.Id))
                    if used_fallback:
                        counts['detail_geometry'].append(eid(element.Id))
            except Exception as exc:
                if recovered:
                    # A problem on an element the view hides anyway is not a legend problem.
                    try:
                        reason = hidden_reason(doc, view, element, label)
                    except Exception:
                        reason = None
                    if reason:
                        counts['plan_region_hidden'].append(u'{0}: {1}'.format(eid(element.Id), reason))
                        continue
                record(label, key, exc)
                continue
            counts['elements'] += 1
            counts['solids'] += parts
            counts['in_scope'] += in_scope
            if materials:
                counts['by_category'][key] += 1
            for uid, material in materials.items():
                found.setdefault(uid, [material, set()])[1].add(key)
    records = []
    for material, keys in found.values():
        label = u'Material [ID {0}]'.format(eid(material.Id))
        try:
            diagnostics.phase('Scan / Material Description and Color', label)
            parameter = material.get_Parameter(DB.BuiltInParameter.ALL_MODEL_DESCRIPTION)
            if parameter is None:
                raise LegendError('Cannot read Material Description.')
            color = material.Color
            if color is None or not color.IsValid:
                raise LegendError('Cannot read Material Graphics Shading color.')
            records.append({'uid': material.UniqueId, 'id': eid(material.Id),
                            'name': material.Name, 'description': parameter.AsString() or '',
                            'rgb': [int(color.Red), int(color.Green), int(color.Blue)],
                            'render_appearance': bool(material.UseRenderAppearanceForShading),
                            'categories': [k for k in CATEGORY_KEYS if k in keys]})
        except Exception as exc:
            record(label, None, exc)
    if issues:
        diagnostics.phase('Scan / Problems found (nothing written)', issues[0]['element'])
        diagnostics.id_input = issues[0]['id_input']
        raise ScanIssues(issues)
    return material_rows(records), counts


def annotations(doc, view):
    # Do not use view-scoped collector: hidden/outside-crop annotations still belong to registry.
    for cls in (DB.FilledRegion, DB.TextNote):
        for element in DB.FilteredElementCollector(doc).OfClass(cls):
            if element.OwnerViewId == view.Id:
                yield element


def check_annotation_dependencies(element):
    diagnostics.phase('Read / Existing annotation dependencies',
                      '{0} [ID {1}]'.format(element.GetType().FullName, eid(element.Id)))
    return check_dependencies(element, (read_data(element) or {}).get('native_dimensions'))


def stamp_new_annotation(element, data):
    diagnostics.phase('Write / New annotation dependency provenance',
                      '{0} [ID {1}]'.format(element.GetType().FullName, eid(element.Id)))
    element.Document.Regenerate()
    report = check_dependencies(element, newly_created=True)
    data['native_dimensions'] = report['native_dimensions']
    write_data(element, data)


def resolve_existing(doc, view, registry, protect_existing=True):
    validate_registry(registry, view.UniqueId)
    editable(doc, view)
    resolved = {}
    registered_ids = set()
    for material_uid, pair in registry['rows'].items():
        resolved[material_uid] = {}
        for role in ('region', 'text'):
            uid = pair[role]
            registered_ids.add(uid)
            element = doc.GetElement(uid)
            if element is not None:
                expected_cls = DB.FilledRegion if role == 'region' else DB.TextNote
                if not isinstance(element, expected_cls):
                    raise LegendError('Registered annotation has wrong Revit class.')
                owner_view = doc.GetElement(element.OwnerViewId)
                validate_row(read_data(element), registry, material_uid, role,
                             owner_view.UniqueId if owner_view is not None else None)
                editable(doc, element)
                if protect_existing:
                    check_annotation_dependencies(element)
            resolved[material_uid][role] = element
    for element in annotations(doc, view):
        data = read_data(element)
        if data is not None and element.UniqueId not in registered_ids:
            raise LegendError('Unregistered/copied tool annotation {0}; no changes made. '
                              'Remove the copied tool annotations or use the original view.'.format(eid(element.Id)))
    return resolved


def registered_views(doc):
    # Includes invalid/copied registry so Update All reports it, never silently drops it.
    return [v for v in DB.FilteredElementCollector(doc).OfClass(DB.View)
            if schema() is not None and v.GetEntity(schema()).IsValid()]


def registration_markers(doc):
    return [e for e in DB.FilteredElementCollector(doc).OfClass(DataStorage)
            if schema() is not None and e.GetEntity(schema()).IsValid()]


def registration_issues(doc):
    issues = []
    for marker in registration_markers(doc):
        try:
            data = read_data(marker)
            validate_stamp(data, 'registration')
            source = doc.GetElement(data['source'])
            if source is None:
                issues.append('Source View no longer exists: {0}; registration {1} retained.'.format(
                    data['source'], eid(marker.Id)))
            elif read_data(source) is None:
                issues.append('Source View registration is missing: {0}; marker retained.'.format(eid(source.Id)))
        except Exception as exc:
            issues.append('Registration {0}: {1}'.format(eid(marker.Id), exc))
    return issues


def maintain_registration(doc, registry):
    matches = []
    for marker in registration_markers(doc):
        data = read_data(marker)
        validate_stamp(data, 'registration')
        if data.get('source') == registry['source'] or data.get('legend') == registry['legend']:
            if data.get('source') != registry['source'] or data.get('legend') != registry['legend']:
                raise LegendError('Registration marker ownership mismatch.')
            matches.append(marker)
    if len(matches) > 1:
        raise LegendError('Duplicate registration markers; existing legend preserved.')
    if not matches:
        marker = DataStorage.Create(doc)
        write_data(marker, stamp('registration', source=registry['source'], legend=registry['legend']))


def new_registry(doc, view, anchor, text_type, categories=None, excluded=()):
    if read_data(view) is not None:
        raise LegendError('This view already has tool metadata. Use Update Current Legend.')
    if any(read_data(element) is not None for element in annotations(doc, view)):
        raise LegendError('Copied/orphan tool annotations detected. No new legend created.')
    return with_settings(stamp('legend', source=view.UniqueId, legend=str(uuid.uuid4()),
                               anchor=[anchor.X, anchor.Y, anchor.Z], text_type=text_type.UniqueId,
                               layout=dict(DEFAULT_LAYOUT), rows={}),
                         categories or DEFAULT_CATEGORIES, excluded)


def filled_type(doc):
    types = list(DB.FilteredElementCollector(doc).OfClass(DB.FilledRegionType))
    owned = []
    for typ in types:
        data = read_data(typ)
        if data is not None:
            validate_stamp(data, 'type')
            if data.get('type_uid') != typ.UniqueId:
                raise LegendError('Copied tool Filled Region Type detected; resolve duplicate type first.')
            owned.append(typ)
    if len(owned) > 1:
        raise LegendError('Multiple owned Filled Region Types found; no new type created.')
    patterns = [p for p in DB.FilteredElementCollector(doc).OfClass(DB.FillPatternElement)
                if p.GetFillPattern().IsSolidFill and p.GetFillPattern().Target == DB.FillPatternTarget.Drafting]
    if not patterns:
        raise LegendError('No Drafting Solid Fill pattern exists.')
    pattern = patterns[0]
    if owned:
        typ = owned[0]
        if typ.ForegroundPatternId != pattern.Id or typ.BackgroundPatternId != INVALID or not typ.IsMasking:
            raise LegendError('Owned Filled Region Type was changed; restore its Solid Fill settings first.')
        return typ, pattern
    if not types:
        raise LegendError('No existing Filled Region Type to duplicate. Create one in the test document first.')
    names = set(element_name(t) for t in types)
    name = 'YSU_ColorLegend'
    suffix = 2
    while name in names:
        name = 'YSU_ColorLegend_Tool_{0}'.format(suffix)
        suffix += 1
    typ = types[0].Duplicate(name)
    typ.ForegroundPatternId = pattern.Id
    typ.BackgroundPatternId = INVALID
    typ.ForegroundPatternColor = DB.Color(0, 0, 0)
    typ.IsMasking = True
    typ.LineWeight = 1
    write_data(typ, stamp('type', type_uid=typ.UniqueId))
    return typ, pattern


def row_stamp(registry, material_uid, role):
    return stamp('row', source=registry['source'], legend=registry['legend'],
                 material=material_uid, role=role)


def rectangle(view, origin, size):
    right = view.RightDirection.Multiply(size)
    down = view.UpDirection.Multiply(-size)
    points = [origin, origin.Add(down), origin.Add(down).Add(right), origin.Add(right)]
    loop = DB.CurveLoop()
    for index in range(4):
        loop.Append(DB.Line.CreateBound(points[index], points[(index + 1) % 4]))
    return List[DB.CurveLoop]([loop])


def region_corner(view, region, size):
    loops = list(region.GetBoundaries())
    if len(loops) != 1:
        return None
    curves = list(loops[0])
    if len(curves) != 4 or any(not isinstance(c, DB.Line) for c in curves):
        return None
    points = [c.GetEndPoint(0) for c in curves]
    xs = [p.DotProduct(view.RightDirection) for p in points]
    ys = [p.DotProduct(view.UpDirection) for p in points]
    if abs(max(xs) - min(xs) - size) > 1e-6 or abs(max(ys) - min(ys) - size) > 1e-6:
        return None
    if any(min(abs(x - min(xs)), abs(x - max(xs))) > 1e-6 or
           min(abs(y - min(ys)), abs(y - max(ys))) > 1e-6 for x, y in zip(xs, ys)):
        return None
    return view.RightDirection.Multiply(min(xs)).Add(view.UpDirection.Multiply(max(ys))).Add(
        view.ViewDirection.Multiply(points[0].DotProduct(view.ViewDirection)))


LEGEND_CATEGORIES = (('Text Notes', DB.BuiltInCategory.OST_TextNotes),
                     ('Detail Items (Filled Region)', DB.BuiltInCategory.OST_DetailComponents))


def require_visible(view, categories):
    """Refuse to write a legend the source view would not display; never change V/G."""
    problems = []
    if view.AreAnnotationCategoriesHidden:
        problems.append('annotation categories are hidden in Visibility/Graphics')
    for label, category in categories:
        if view.GetCategoryHidden(as_element_id(category)):
            problems.append('{0} category is hidden'.format(label))
    if problems:
        raise LegendError('Source view would not display the legend ({0}). View settings are '
                          'not changed by this tool; make them visible or use another view.'.format(
                              '; '.join(problems)))


def text_border_pad(text_type):
    """Sheet-unit border offset; TextElement.Height/Width exclude the border."""
    shown = text_type.get_Parameter(DB.BuiltInParameter.TEXT_BOX_VISIBILITY)
    if shown is None or not shown.AsInteger():
        return 0.0
    offset = text_type.get_Parameter(DB.BuiltInParameter.LEADER_OFFSET_SHEET)
    if offset is None:
        raise LegendError('Text type shows a border but its Leader/Border Offset cannot be read.')
    return offset.AsDouble()


def measure_text(doc, view, note, text_type, width, pad):
    """Row height from the documented TextElement content Height (sheet units, after Regenerate).

    0.1.2 measured note.get_BoundingBox(view); in Revit 2026.4 that returned null for the
    new TextNote. Per API contract BoundingBox is null when the view box cannot be calculated
    and there is no model box, so it is not a reliable measurement inside the creating transaction.
    """
    active = doc.ActiveView
    evidence = {'text_note': eid(note.Id), 'owner_view': eid(note.OwnerViewId),
                'source_view': eid(view.Id),
                'active_view': eid(active.Id) if active is not None else None,
                'text_type': u'{0} [ID {1}]'.format(element_name(text_type), eid(text_type.Id)),
                'view_scale': view.Scale, 'requested_width_ft': width, 'border_pad_ft': pad,
                'measurement': 'TextElement.Height/Width sheet units after Regenerate'}
    diagnostics.detail = json.dumps(evidence, ensure_ascii=True, sort_keys=True)
    evidence.update(height_ft=note.Height, width_ft=note.Width, label_chars=len(note.Text or ''))
    diagnostics.detail = json.dumps(evidence, ensure_ascii=True, sort_keys=True)
    print('Color Legend text layout: ' + diagnostics.detail)
    if note.OwnerViewId != view.Id:
        raise LegendError('TextNote is not owned by the source view; no partial legend retained.')
    for value in (evidence['height_ft'], evidence['width_ft']):
        if value is None or math.isnan(value) or math.isinf(value) or value <= 0:
            raise LegendError('Revit returned an invalid TextNote size (Height={0}, Width={1}); '
                              'no partial legend retained.'.format(evidence['height_ft'], evidence['width_ft']))
    category = note.Category
    if category is None:
        raise LegendError('TextNote has no category; cannot confirm it is visible.')
    require_visible(view, [('TextNote category ' + category.Name, category.Id)])
    return evidence['height_ft']


def delete_annotation(doc, element):
    if element is None:
        return
    # Use the same proven sketch ownership/provenance as update. A newly added
    # manual dimension is never admitted to the deletion cascade whitelist.
    allowed = set(check_annotation_dependencies(element)['allowed_ids'])
    diagnostics.phase('Write / Delete owned annotation', 'ID {0}'.format(eid(element.Id)))
    removed = set(eid(x) for x in doc.Delete(element.Id))
    if not removed.issubset(allowed):
        raise LegendError('Delete affected unexpected dependent elements {0}; rolling back.'.format(sorted(removed - allowed)))


def apply_rows(doc, view, registry, rows):
    resolved = resolve_existing(doc, view, registry)
    text_type = doc.GetElement(registry['text_type'])
    if not isinstance(text_type, DB.TextNoteType):
        raise LegendError('Saved TextNoteType no longer exists; existing legend preserved.')
    diagnostics.phase('Read / Legend visibility and text type')
    require_visible(view, LEGEND_CATEGORIES)
    pad = text_border_pad(text_type)
    changes = delta(registry['rows'], rows)
    layout = registry['layout']
    scale = view.Scale
    size = layout['box_mm'] * MM * scale
    gap = layout['gap_mm'] * MM * scale
    row_gap = layout['row_gap_mm'] * MM * scale
    width = layout['text_width_mm'] * MM
    width = max(width, DB.TextNote.GetMinimumAllowedWidth(doc, text_type.Id))
    width = min(width, DB.TextNote.GetMaximumAllowedWidth(doc, text_type.Id))
    anchor = DB.XYZ(*registry['anchor'])
    result_rows = {}
    for material_uid in changes['remove']:
        diagnostics.phase('Write / Remove obsolete row', 'Material UniqueId ' + material_uid)
        for element in resolved[material_uid].values():
            delete_annotation(doc, element)
    typ, pattern = filled_type(doc) if rows else (None, None)
    repaired = 0
    y_offset = 0.0
    for row in rows:
        material_uid = row['uid']
        diagnostics.phase('Write / Create or update row', 'Material UniqueId ' + material_uid)
        previous = resolved.get(material_uid, {})
        region = previous.get('region')
        note = previous.get('text')
        origin = anchor.Add(view.UpDirection.Multiply(-y_offset))
        # Left/Top alignment: TextNote position is the top-left of its content area
        # (TextNote.Create API docs); a shown border is drawn pad outside that area.
        note_origin = origin.Add(view.RightDirection.Multiply(size + gap + pad * scale)).Add(
            view.UpDirection.Multiply(-pad * scale))
        if region is not None:
            diagnostics.phase('Write / Move or replace Filled Region', 'ID {0}'.format(eid(region.Id)))
            corner = region_corner(view, region, size)
            if corner is None:
                # Scale/layout/hand-edited boundary changed: replace this owned box only.
                delete_annotation(doc, region)
                region = None
            else:
                DB.ElementTransformUtils.MoveElement(doc, region.Id, origin.Subtract(corner))
        if region is None:
            diagnostics.phase('Write / FilledRegion.Create', 'Material UniqueId ' + material_uid)
            region = DB.FilledRegion.Create(doc, typ.Id, view.Id, rectangle(view, origin, size))
            stamp_new_annotation(region, row_stamp(registry, material_uid, 'region'))
            if material_uid in changes['keep']:
                repaired += 1
        elif region.GetTypeId() != typ.Id:
            raise LegendError('Owned box type was changed manually; update aborted.')
        diagnostics.phase('Write / OverrideGraphicSettings', 'Filled Region ID {0}'.format(eid(region.Id)))
        if region.Category is None:
            raise LegendError('Filled Region has no category; cannot confirm it is visible.')
        require_visible(view, [('Filled Region category ' + region.Category.Name, region.Category.Id)])
        color = DB.Color(*row['rgb'])
        settings = DB.OverrideGraphicSettings()
        settings.SetSurfaceForegroundPatternId(pattern.Id)
        settings.SetSurfaceForegroundPatternColor(color)
        settings.SetSurfaceForegroundPatternVisible(True)
        settings.SetSurfaceBackgroundPatternVisible(False)
        settings.SetCutForegroundPatternId(pattern.Id)
        settings.SetCutForegroundPatternColor(color)
        settings.SetCutForegroundPatternVisible(True)
        settings.SetProjectionLineColor(color)
        settings.SetCutLineColor(color)
        settings.SetSurfaceTransparency(0)
        settings.SetHalftone(False)
        view.SetElementOverrides(region.Id, settings)
        if note is None:
            diagnostics.phase('Write / TextNote.Create', 'Material UniqueId ' + material_uid)
            options = DB.TextNoteOptions(text_type.Id)
            options.HorizontalAlignment = DB.HorizontalTextAlignment.Left
            options.VerticalAlignment = DB.VerticalTextAlignment.Top
            note = DB.TextNote.Create(doc, view.Id, note_origin, width, row['label'], options)
            stamp_new_annotation(note, row_stamp(registry, material_uid, 'text'))
            if material_uid in changes['keep']:
                repaired += 1
        else:
            diagnostics.phase('Write / Update TextNote', 'ID {0}'.format(eid(note.Id)))
            if note.BaseDirection.DotProduct(view.RightDirection) < 0.999999:
                raise LegendError('Owned text was rotated manually; restore orientation before updating.')
            if note.GetTypeId() != text_type.Id:
                note.ChangeTypeId(text_type.Id)
            note.Text = row['label']
            note.Width = width
            note.HorizontalAlignment = DB.HorizontalTextAlignment.Left
            note.VerticalAlignment = DB.VerticalTextAlignment.Top
            note.Coord = note_origin
        diagnostics.phase('Write / Text layout', 'TextNote ID {0}'.format(eid(note.Id)))
        doc.Regenerate()
        # Wrapped multi-line text grows Height; the next row starts below text or box.
        text_height = measure_text(doc, view, note, text_type, width, pad)
        y_offset += max(size, (text_height + 2 * pad) * scale) + row_gap
        # Verify stored override values; actual display is a separate Revit acceptance check.
        diagnostics.phase('Write / Override readback', 'Filled Region ID {0}'.format(eid(region.Id)))
        actual = view.GetElementOverrides(region.Id).SurfaceForegroundPatternColor
        if [int(actual.Red), int(actual.Green), int(actual.Blue)] != [int(c) for c in row['rgb']]:
            raise LegendError('Filled Region override readback failed.')
        result_rows[material_uid] = {'region': region.UniqueId, 'text': note.UniqueId}
    updated = dict(registry)
    updated['rows'] = result_rows
    diagnostics.phase('Write / Extensible Storage registration')
    maintain_registration(doc, updated)
    write_data(view, updated)
    if read_data(view) != updated:
        raise LegendError('Legend registration readback failed.')
    diagnostics.phase('Write / Final ownership and registry validation')
    # This is identity/readback validation, not permission to mutate an existing
    # annotation. Existing dependencies were checked BEFORE writes; new ones have
    # explicit creation provenance. Do not reclassify new native constraints as manual.
    resolve_existing(doc, view, updated, protect_existing=False)
    return {'rows': len(rows), 'added': len(changes['add']), 'removed': len(changes['remove']),
            'retained': len(changes['keep']), 'repaired_annotations': repaired}


def update(doc, view, registry, rows):
    diagnostics.phase('Write / Update legend')
    return atomic(AtomicTransaction(doc, 'YSU Create Color Legend'),
                  lambda: apply_rows(doc, view, registry, rows))


def load_registry(doc, view):
    """Validated registry (format 1 or 2) of the source view; ownership checked before any UI."""
    diagnostics.source = u'{0} [ID {1}]'.format(view.Name, eid(view.Id))
    diagnostics.phase('Read / Ownership validation')
    registry = read_data(view)
    if registry is None:
        raise LegendError('No registered tool legend in this view. Use Create Legend first.')
    resolve_existing(doc, view, registry)
    return registry


def refresh(doc, view):
    """Update All: each legend's own saved categories and exclusions, no dialog."""
    registry = load_registry(doc, view)
    categories, excluded = legend_settings(registry)
    scanned, counts = scan(doc, view, categories)  # any failure exits BEFORE update/delete
    rows = legend_rows(scanned, excluded)
    added = new_rows(rows, registry['rows'])
    result = update(doc, view, with_settings(registry, categories, excluded), rows)
    result['new_items'] = [row['label'] for row in added]
    result['excluded_in_scan'] = len(scanned) - len(rows)
    return result, rows, counts


def pick_anchor(doc, uidoc, view):
    """Temporary work plane exists only during pick, always rolled back before creation."""
    uidoc.ActiveView = view
    editable(doc, view)
    diagnostics.phase('Pick / Temporary Work Plane')
    adapter = AtomicTransaction(doc, 'YSU temporary point-pick plane')
    adapter.start()
    failure_trace = None
    try:
        view.SketchPlane = DB.SketchPlane.Create(doc, DB.Plane.CreateByNormalAndOrigin(
            view.ViewDirection, DB.XYZ(0, 0, view.GenLevel.ProjectElevation)))
        if adapter.tx.Commit() != DB.TransactionStatus.Committed:
            raise LegendError('Cannot prepare point picker: ' + '; '.join(adapter.failures.messages))
        return uidoc.Selection.PickPoint('Pick the top-left corner of the color legend (Esc to cancel)')
    except Exception:
        failure_trace = traceback.format_exc()
        raise
    finally:
        try:
            adapter.rollback()
        except Exception as rollback_error:
            if failure_trace:
                rollback_error.original_traceback = failure_trace
            raise
