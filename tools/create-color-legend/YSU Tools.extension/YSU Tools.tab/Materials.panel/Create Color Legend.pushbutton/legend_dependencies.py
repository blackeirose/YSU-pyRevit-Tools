# -*- coding: utf-8 -*-
"""Dependency evidence, separate from registry identity (Revit 2026)."""
import json
from pyrevit import DB
from legend_core import LegendError
from legend_ids import id_value


def describe_element(element):
    category = element.Category
    return {'id': id_value(element.Id), 'uid': element.UniqueId,
            'class': element.GetType().FullName,
            'category': None if category is None else
            {'id': id_value(category.Id), 'name': category.Name},
            'owner_view': id_value(element.OwnerViewId)}


def dependency_evidence(element, newly_created=False):
    """Read actual classes and relationships; a filtered ID is not proof of a manual dimension."""
    doc = element.Document
    report = {'target': describe_element(element), 'new_in_transaction': newly_created,
              'dependencies': [], 'errors': []}
    try:
        collection = element.GetDependentElements(None)
        ids = list(collection)
        dimension_filter = DB.ElementClassFilter(DB.Dimension)
        filtered = list(element.GetDependentElements(dimension_filter))
        report.update(count=collection.Count, enumerated_count=len(ids),
                      dimension_filter_ids=[id_value(i) for i in filtered])
        if collection.Count != len(ids):
            report['errors'].append('Dependent collection Count/content mismatch')
        objects = dict((id_value(i), doc.GetElement(i)) for i in ids + filtered)
        # Only a Sketch with the exact target OwnerId establishes ownership.
        membership, structural = {}, set([id_value(element.Id)])
        for sketch in list(objects.values()):
            if isinstance(element, DB.FilledRegion) and isinstance(sketch, DB.Sketch):
                if sketch.OwnerId != element.Id:
                    continue
                structural.add(id_value(sketch.Id))
                members = list(sketch.GetAllElements())
                if sketch.SketchPlane is not None:
                    members.append(sketch.SketchPlane.Id)
                for member_id in members:
                    key = id_value(member_id)
                    objects[key] = doc.GetElement(member_id)
                    membership[key] = sketch.UniqueId
                    if isinstance(objects[key], (DB.CurveElement, DB.SketchPlane, DB.ReferencePlane)):
                        structural.add(key)
        # A dimension/tag can attach to a boundary curve instead of the region.
        # Inspect these logical children too; do not assume the parent query is recursive.
        for key in list(structural - set([id_value(element.Id)])):
            for child_id in objects[key].GetDependentElements(None):
                objects[id_value(child_id)] = doc.GetElement(child_id)
        native = {}
        allowed = set(structural)
        for key, dep in sorted(objects.items()):
            if dep is None:
                report['errors'].append('Cannot resolve dependent ID {0}'.format(key))
                continue
            item = describe_element(dep)
            item.update(direct=key in [id_value(i) for i in ids],
                        filter_returned=key in report['dimension_filter_ids'],
                        filter_passes=dimension_filter.PassesFilter(dep),
                        sketch_member_of=membership.get(key))
            report['dependencies'].append(item)
            if isinstance(dep, DB.Sketch):
                item['sketch_owner'] = id_value(dep.OwnerId)
            same_view = dep.OwnerViewId in (element.OwnerViewId, DB.ElementId.InvalidElementId)
            if isinstance(dep, DB.Dimension):
                refs = []
                item['references'] = refs
                for ref in dep.References:
                    refs.append({'element': id_value(ref.ElementId),
                                 'linked': id_value(ref.LinkedElementId),
                                 'stable': ref.ConvertToStableRepresentation(doc)})
                # Require actual sketch membership AND local references. An empty
                # native reference array is recorded, not confused with read failure.
                internal = (key in membership and same_view and
                            all(r['element'] in structural and r['linked'] == -1 for r in refs))
                if internal:
                    native[dep.UniqueId] = {'sketch': membership[key], 'references': refs}
                    allowed.add(key)
                item['relationship'] = 'owned-sketch-dimension' if internal else 'external-or-unresolved-dimension'
            elif key in structural and same_view:
                item['relationship'] = 'owned-sketch-structure' if key != id_value(element.Id) else 'target-itself'
            else:
                allowed.discard(key)
                item['relationship'] = 'unresolved-dependent'
        report['native_dimensions'] = native
        report['allowed_ids'] = sorted(allowed)
        report['blocked_ids'] = sorted(set(objects) - allowed)
    except Exception as exc:
        report['errors'].append(str(exc))
        print('Color Legend dependency evidence: ' + json.dumps(report, ensure_ascii=True, sort_keys=True))
        raise  # preserve API traceback; never turn read failure into an empty result
    return report


def check_dependencies(element, saved_native=None, newly_created=False):
    report = dependency_evidence(element, newly_created)
    native = report['native_dimensions']
    # Only freshly created annotations can establish provenance. Never adopt a
    # pre-existing sketch dimension just because it is inside the region sketch.
    changed = [] if newly_created else [uid for uid, value in native.items()
                                        if (saved_native or {}).get(uid) != value]
    if newly_created or report['blocked_ids'] or report['errors'] or changed:
        print('Color Legend dependency evidence: ' + json.dumps(report, ensure_ascii=True, sort_keys=True))
    if report['blocked_ids'] or report['errors'] or changed:
        changed_ids = [item['id'] for item in report['dependencies'] if item['uid'] in changed]
        raise LegendError('Annotation {0}: protected external/manual or unverified dependencies {1}; '
                          'native dimension provenance changed {2}. See dependency evidence; '
                          'existing annotations preserved by abort/rollback.'.format(
                              id_value(element.Id), report['blocked_ids'], changed_ids))
    return report
