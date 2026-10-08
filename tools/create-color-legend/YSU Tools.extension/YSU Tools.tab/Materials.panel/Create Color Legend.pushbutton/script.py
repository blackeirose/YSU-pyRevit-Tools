# -*- coding: utf-8 -*-
"""Create Color Legend -- local Revit 2026 candidate, runtime acceptance pending."""
__title__ = 'Create Color\nLegend'
__author__ = 'YSU'

from pyrevit import DB, forms, revit, script
from Autodesk.Revit.Exceptions import OperationCanceledException
from legend_core import (VERSION, LegendError, OperationState, CATEGORY_LABELS, DEFAULT_CATEGORIES,
                         legend_settings, with_settings, apply_selection, legend_rows, new_rows)
import traceback
import legend_revit as engine
import legend_ui as ui

TITLE = 'Create Color Legend'
PLAN_REGION_NOTE = u'已忽略 Plan Region 局部範圍，依主要 View Range 掃描。'


def failure_report(exc, show_alert=True):
    message = engine.diagnostics.summary(exc)
    print(message)
    try:
        active = revit.doc.ActiveView
        print(u'Active View at failure: {0} [ID {1}]'.format(active.Name, engine.eid(active.Id)))
    except Exception as view_error:
        print(u'Active View at failure: unavailable ({0})'.format(view_error))
    for issue in getattr(exc, 'issues', []):
        print(u'掃描問題：{0}（{1}）：{2}'.format(issue['element'], issue['stage'], issue['reason']))
    original = getattr(exc, 'original_traceback', None)
    if original:
        print('Original error traceback:\n' + original)
    print(traceback.format_exc())
    if show_alert:
        forms.alert(u'圖例操作未完成。\n\n{0}\n\n完整 traceback 請查看 pyRevit output。'.format(message),
                    title=TITLE, warn_icon=True)


def source_view(doc, uidoc):
    active = doc.ActiveView
    if engine.supported_plan(active):
        return active
    if not isinstance(active, DB.ViewSheet):
        raise LegendError(u'請從 Floor Plan 或有平面 Viewport 的 Sheet 執行。')
    selected = [doc.GetElement(i) for i in uidoc.Selection.GetElementIds()]
    selected = [v for v in selected if isinstance(v, DB.Viewport) and v.OwnerViewId == active.Id]
    pool = selected if selected else [doc.GetElement(i) for i in active.GetAllViewports()]
    views = [doc.GetElement(v.ViewId) for v in pool]
    views = [v for v in views if engine.supported_plan(v)]
    if not views:
        raise LegendError(u'所選 Viewport（或此 Sheet）沒有適用的 Floor Plan。請選取平面 Viewport 再執行。')
    if len(views) == 1:
        return views[0]
    choices = dict(('{0}  [ID {1}]'.format(v.Name, engine.eid(v.Id)), v) for v in views)
    choice = forms.SelectFromList.show(sorted(choices), title=u'選擇來源 Floor Plan', multiselect=False,
                                       button_name='Use View')
    return choices.get(choice)


def choose_text_type(doc):
    types = list(DB.FilteredElementCollector(doc).OfClass(DB.TextNoteType))
    if not types:
        raise LegendError(u'文件沒有可用的 TextNoteType。')
    choices = dict(('{0}  [ID {1}]'.format(engine.element_name(t), engine.eid(t.Id)), t) for t in types)
    choice = forms.SelectFromList.show(sorted(choices), title=u'選擇整份圖例的文字類型',
                                       button_name='Use Text Type', multiselect=False)
    return choices.get(choice)


def owner_handle():
    try:
        from pyrevit.api import AdWindows
        return AdWindows.ComponentManager.ApplicationWindow
    except Exception:
        return None  # dialog still works without an owner


def category_text(keys):
    return u', '.join(CATEGORY_LABELS.get(k, k) for k in keys)


def report(view, result, rows, counts):
    print(u'View: {0} [ID {1}] -- 已提交更新'.format(view.Name, engine.eid(view.Id)))
    print(u'列數 {rows}；新增 {added}；移除 {removed}；保留 {retained}；補回註解 {repaired_annotations}'.format(**result))
    print(u'Category：{0}；檢查元素 {1}，solids／表面 {2}，其中在主要範圍內 {3}'.format(
        category_text(counts.get('categories', [])), counts.get('elements', 0), counts.get('solids', 0),
        counts.get('in_scope', 0)))
    if result.get('new_items'):
        print(u'新增項目（新材質預設納入）：' + u'；'.join(result['new_items']))
    if result.get('excluded_in_scan'):
        print(u'依此圖例的排除設定未顯示：{0} 個材質'.format(result['excluded_in_scan']))
    if counts.get('plan_regions'):
        listed = lambda items: u', '.join(u'{0}'.format(x) for x in items) or u'無'
        print(PLAN_REGION_NOTE + u'（Plan Region {0} 個；View collector 外補收元素：{1}；'
              u'依 View 可見性規則排除：{2}；改用 Detail Level 幾何：{3}）'.format(
                  counts['plan_regions'], listed(counts['plan_region_added']),
                  listed(counts['plan_region_hidden']), listed(counts['detail_geometry'])))
    for row in rows:
        if row['missing_description']:
            print(u'未填 Description：Material {0} [ID {1}]'.format(row['name'], row['id']))
        if row['render_appearance']:
            print(u'Use Render Appearance=True：Material {0} [ID {1}]，讀取 Material.Color RGB={2}'.format(
                row['name'], row['id'], row['rgb']))


def main():
    engine.diagnostics = OperationState()
    doc, uidoc = revit.doc, revit.uidoc
    if doc is None or uidoc is None:
        raise LegendError(u'請先開啟 Revit 專案文件。')
    if doc.IsFamilyDocument:
        raise LegendError(u'目前是 Family Editor，請切換至專案文件。')
    if doc.IsReadOnly:
        raise LegendError(u'目前文件為唯讀，無法建立或更新圖例。')
    if doc.IsModifiable:
        raise LegendError(u'目前文件有未結束的交易；請待目前操作結束後重試。')
    if doc.Application.VersionNumber != '2026':
        raise LegendError(u'此候選版僅針對 Revit 2026，其他版本尚未驗證。')
    action = forms.CommandSwitchWindow.show(
        ['Create Legend', 'Update Current Legend', 'Update All Tool Legends'],
        message=u'Create Color Legend — 選擇操作')
    if not action:
        return
    print('Create Color Legend {0} | Revit {1}'.format(VERSION, doc.Application.VersionNumber))
    print(u'結果僅代表本次操作；候選版的 Revit 視覺與跨樓層驗收仍待完成。')
    if action == 'Update All Tool Legends':
        views = engine.registered_views(doc)
        issues = engine.registration_issues(doc)
        for issue in issues:
            print(u'略過：' + issue)
        if not views:
            forms.alert(u'沒有可更新的工具圖例。請查看報告；若尚未建立，請先在來源平面 Create Legend。', title=TITLE)
            return
        succeeded, failed = 0, len(issues)
        processed, skipped, added = 0, 0, 0
        for view in sorted(views, key=lambda v: v.UniqueId):
            processed += 1
            engine.diagnostics = OperationState()
            engine.diagnostics.source = u'{0} [ID {1}]'.format(view.Name, engine.eid(view.Id))
            try:
                # Each legend: its own saved Category / exclusions, own transaction; no dialog.
                result, rows, counts = engine.refresh(doc, view)
                engine.diagnostics.phase('Report / Result')
                report(view, result, rows, counts)
                added += len(result.get('new_items', []))
                succeeded += 1
            except Exception as exc:
                failed += 1
                failure_report(exc, show_alert=False)
                if engine.diagnostics.transaction == 'rollback_unconfirmed':
                    skipped = len(views) - processed
                    print(u'復原狀態不明，停止後續批次；尚未處理的圖例保留。')
                    break
        forms.alert(u'批次結果：成功 {0}，失敗／略過 {1}，未處理 {2}；新增材質 {3} 項。\n'
                    u'每張圖例各自一個交易：失敗者保留原圖例與設定，成功者已提交。請查看 pyRevit 結果報告。'.format(
                        succeeded, failed, skipped, added), title=TITLE, warn_icon=bool(failed))
        return
    engine.diagnostics.phase('Read / Source View or Sheet Viewport')
    engine.diagnostics.source = u'{0} [ID {1}] (entry)'.format(doc.ActiveView.Name, engine.eid(doc.ActiveView.Id))
    view = source_view(doc, uidoc)
    if view is None:
        return
    engine.diagnostics.source = u'{0} [ID {1}]'.format(view.Name, engine.eid(view.Id))
    engine.diagnostics.phase('Read / Legend registration')
    registry = engine.read_data(view)
    if action == 'Create Legend' and registry is not None:
        if not forms.alert(u'此來源 View 已有工具圖例。要更新既有圖例嗎？', title=TITLE, yes=True, no=True):
            return
        action = 'Update Current Legend'
    if action == 'Update Current Legend':
        outcome = update_current(doc, view)
    else:
        outcome = create_legend(doc, uidoc, view)
    if outcome is None:
        return  # cancelled or nothing to write; no model change and no new setting
    result, rows, counts = outcome
    engine.diagnostics.phase('Report / Result')
    report(view, result, rows, counts)
    note = u'\n' + PLAN_REGION_NOTE if counts.get('plan_regions') else u''
    forms.alert(u'圖例已更新：{0} 列（Category：{1}）。{2}\n缺少 Description 的材質與詳細資訊請查看結果報告。'.format(
        result['rows'], category_text(counts.get('categories', [])), note), title=TITLE)


def create_legend(doc, uidoc, view):
    """Category -> scan -> materials -> text type -> point -> write. Every cancel writes nothing."""
    engine.diagnostics.phase('Select / Categories')
    categories = ui.choose_categories(DEFAULT_CATEGORIES, owner_handle())
    if not categories:
        return None
    scanned, counts = engine.scan(doc, view, categories)  # problems raise before any dialog/write
    if not scanned:
        forms.alert(u'掃描成功，但範圍內沒有符合所選 Category（{0}）的材質；未建立圖例。'.format(
            category_text(categories)), title=TITLE)
        return None
    engine.diagnostics.phase('Select / Materials')
    checked = ui.choose_materials(scanned, {}, [], 'create', owner_handle())
    if checked is None:
        return None
    if not checked:
        forms.alert(u'未勾選任何材質；不建立空圖例。', title=TITLE)
        return None
    excluded = apply_selection([r['uid'] for r in scanned], [], checked)
    rows = legend_rows(scanned, excluded)
    engine.diagnostics.phase('Read / Legend visibility')
    engine.require_visible(view, engine.LEGEND_CATEGORIES)  # before asking for type/point
    engine.diagnostics.phase('Select / Text type')
    text_type = choose_text_type(doc)
    if text_type is None:
        return None
    anchor = engine.pick_anchor(doc, uidoc, view)
    engine.diagnostics.phase('Read / Prepare new registration')
    registry = engine.new_registry(doc, view, anchor, text_type, categories, excluded)
    result = engine.update(doc, view, registry, rows)
    return result, rows, counts


def update_current(doc, view):
    """Adjust Category -> rescan -> materials (previous exclusions kept) -> write.
    Settings are written with the rows in one transaction; cancel or failure changes neither."""
    registry = engine.load_registry(doc, view)
    categories, excluded = legend_settings(registry)
    engine.diagnostics.phase('Select / Categories')
    categories = ui.choose_categories(categories, owner_handle())
    if not categories:
        return None
    scanned, counts = engine.scan(doc, view, categories)
    uids = [r['uid'] for r in scanned]
    if scanned:
        engine.diagnostics.phase('Select / Materials')
        checked = ui.choose_materials(scanned, registry['rows'], excluded, 'update', owner_handle())
        if checked is None:
            return None
        excluded = apply_selection(uids, excluded, checked)
    rows = legend_rows(scanned, excluded)
    if not rows and registry['rows']:
        reason = (u'所有材質都未勾選' if scanned else
                  u'掃描成功，但所選 Category（{0}）在範圍內沒有材質'.format(category_text(categories)))
        if not forms.alert(u'{0}。\n確認後會移除此圖例的所有工具列（色塊與文字）；Category 與勾選設定會保留，'
                           u'之後可再次 Update Current Legend 恢復。\n要繼續嗎？'.format(reason),
                           title=TITLE, yes=True, no=True):
            return None
    elif not rows and not scanned:
        forms.alert(u'掃描成功，但所選 Category（{0}）在範圍內沒有材質；圖例目前也沒有列，未變更。'.format(
            category_text(categories)), title=TITLE)
        return None
    result = engine.update(doc, view, with_settings(registry, categories, excluded), rows)
    result['new_items'] = [row['label'] for row in new_rows(rows, registry['rows'])]
    result['excluded_in_scan'] = len(scanned) - len(rows)
    return result, rows, counts


if __name__ == '__main__':
    try:
        main()
    except OperationCanceledException:
        pass
    except Exception as exc:
        failure_report(exc)
