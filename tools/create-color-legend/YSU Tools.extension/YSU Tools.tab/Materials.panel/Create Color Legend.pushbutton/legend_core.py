# -*- coding: utf-8 -*-
"""Revit-independent identity, ordering and ownership rules (IronPython 2.7)."""
import math
import re
import traceback

VERSION = '0.2.0-candidate'
OWNER = 'YSU.CreateColorLegend'
SCHEMA_VERSION = 1  # row / type / registration stamps
LEGACY_LEGEND_FORMAT = 1  # 0.1.x legend registry: Casework only, no exclusions
LEGEND_FORMAT = 2  # 0.2.x legend registry: categories + excluded Material UniqueIds
MISSING_DESCRIPTION = u'未填 Description'
DEFAULT_LAYOUT = {'box_mm': 4.0, 'gap_mm': 2.0,
                  'row_gap_mm': 2.0, 'text_width_mm': 65.0}

# Stable BuiltInCategory names are the persisted keys; labels are display only.
# rule: 'geometry' = per-solid face materials; the others read one compound layer.
CATEGORIES = [
    ('OST_Casework', u'Casework', 'geometry'),
    ('OST_GenericModel', u'Generic Models', 'geometry'),
    ('OST_Walls', u'Walls', 'wall_exterior'),
    ('OST_Floors', u'Floors', 'floor_top'),
    ('OST_Ceilings', u'Ceilings', 'ceiling_bottom'),
]
CATEGORY_KEYS = [key for key, _, _ in CATEGORIES]
CATEGORY_LABELS = dict((key, label) for key, label, _ in CATEGORIES)
CATEGORY_RULES = dict((key, rule) for key, _, rule in CATEGORIES)
DEFAULT_CATEGORIES = ['OST_Casework']


class LegendError(Exception):
    pass


class ScanIssues(LegendError):
    """Scan exceptions / unsupported construction / unresolved material: never an empty result."""
    SHOWN = 12

    def __init__(self, issues):
        self.issues = list(issues)
        lines = [u'- {0}: {1}'.format(i['element'], i['reason']) for i in self.issues]
        more = len(lines) - self.SHOWN
        text = u'掃描有 {0} 個項目無法可靠處理；未寫入，既有圖例與設定保留。\n{1}'.format(
            len(lines), u'\n'.join(lines[:self.SHOWN]))
        if more > 0:
            text += u'\n…另 {0} 項，完整清單見 pyRevit output。'.format(more)
        LegendError.__init__(self, text)
        traces = [i['traceback'] for i in self.issues if i.get('traceback')]
        if traces:
            self.original_traceback = u'\n'.join(traces)


class OperationState(object):
    """Per-legend diagnostics, never an inferred global document/rollback guarantee."""
    def __init__(self):
        self.stage = 'Preflight'
        self.source = u'尚未解析'
        self.element = u'無'
        self.id_input = u'無'
        self.transaction = 'not_started'
        self.detail = u''

    def phase(self, stage, element=None):
        self.stage = stage
        self.element = element or u'無'
        self.id_input = u'無'
        self.detail = u''

    def summary(self, error):
        states = {
            'not_started': u'本份圖例尚未開始寫入交易；失敗發生於寫入前。',
            'started': u'交易已開始，但尚未取得確認的結束狀態；請停止並檢查文件。',
            'rolled_back': u'本份操作已進入交易，且交易／交易群組狀態確認 rollback 完成。',
            'rollback_unconfirmed': u'ROLLBACK UNCONFIRMED：無法確認交易復原；請停止並檢查文件。',
            'committed': u'本份圖例已提交；此錯誤發生在提交後，不代表圖例未修改。',
        }
        text = u'階段：{0}\n來源 View：{1}\n相關元素：{2}\nID 輸入：{3}\n狀態：{4}\n原始錯誤：{5}'.format(
            self.stage, self.source, self.element, self.id_input,
            states.get(self.transaction, states['rollback_unconfirmed']), error)
        if self.detail:
            text += u'\n診斷：' + self.detail
        return text


def natural_key(value):
    return tuple((1, int(part)) if part.isdigit() else (0, part.lower())
                 for part in re.split(r'(\d+)', value))


def material_rows(records):
    """Deduplicate only document Material.UniqueId; preserve raw Description."""
    result = {}
    for record in records:
        uid = record['uid']
        if not uid:
            raise LegendError('Material UniqueId missing.')
        item = dict(record)
        description = item.get('description') or ''
        item['missing_description'] = not description.strip()
        item['label'] = MISSING_DESCRIPTION if item['missing_description'] else description
        rgb = item['rgb']
        if len(rgb) != 3 or any(int(c) != c or c < 0 or c > 255 for c in rgb):
            raise LegendError('Invalid Material.Color RGB.')
        if uid in result and result[uid] != item:
            raise LegendError('Conflicting material readings: ' + uid)
        result[uid] = item
    return sorted(result.values(), key=lambda item: (natural_key(item['label']), item['uid']))


def delta(old_rows, new_rows, scan_ok=True):
    if not scan_ok:
        raise LegendError('Scan failed; existing legend must be preserved.')
    old = set(old_rows)
    new = set(row['uid'] for row in new_rows)
    return {'keep': old & new, 'add': new - old, 'remove': old - new}


def stamp(kind, **fields):
    data = dict(fields)
    data.update(owner=OWNER, version=SCHEMA_VERSION, kind=kind)
    return data


def validate_stamp(data, kind):
    if not isinstance(data, dict) or data.get('owner') != OWNER or data.get('version') != SCHEMA_VERSION or data.get('kind') != kind:
        raise LegendError('Ownership/schema mismatch; no changes made.')


def validate_categories(categories):
    if (not isinstance(categories, list) or not categories or len(set(categories)) != len(categories)
            or any(key not in CATEGORY_KEYS for key in categories)):
        raise LegendError('Invalid legend category setting: {0!r}'.format(categories))
    return categories


def validate_registry(data, view_uid):
    """Accept the 0.1.x (format 1) and 0.2.x (format 2) legend registry."""
    if (not isinstance(data, dict) or data.get('owner') != OWNER or data.get('kind') != 'legend'
            or data.get('version') not in (LEGACY_LEGEND_FORMAT, LEGEND_FORMAT)):
        raise LegendError('Ownership/schema mismatch; no changes made.')
    if data.get('version') == LEGEND_FORMAT:
        validate_categories(data.get('categories'))
        excluded = data.get('excluded')
        if not isinstance(excluded, list) or len(set(excluded)) != len(excluded) or not all(excluded):
            raise LegendError('Invalid excluded material setting.')
    elif 'categories' in data or 'excluded' in data:
        raise LegendError('Legacy legend registry carries newer settings; no changes made.')
    if data.get('source') != view_uid:
        raise LegendError('Copied View metadata detected. Original legend will not be changed. '
                          'Use an independent view without copied tool annotations/metadata.')
    if not data.get('legend') or not data.get('text_type'):
        raise LegendError('Incomplete legend registration.')
    anchor = data.get('anchor', [])
    if len(anchor) != 3 or not all(isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x) for x in anchor):
        raise LegendError('Invalid legend anchor.')
    layout = data.get('layout', {})
    for key in DEFAULT_LAYOUT:
        val = layout.get(key)
        if not isinstance(val, (int, float)) or not 0 < val <= 500:
            raise LegendError('Invalid layout: ' + key)
    rows = data.get('rows')
    if not isinstance(rows, dict):
        raise LegendError('Invalid row registry.')
    all_ids = []
    for material_uid, pair in rows.items():
        if not material_uid or not isinstance(pair, dict) or set(pair) != set(['region', 'text']):
            raise LegendError('Invalid row mapping.')
        for uid in pair.values():
            if not uid:
                raise LegendError('Missing annotation UniqueId in registration.')
            all_ids.append(uid)
    if len(all_ids) != len(set(all_ids)):
        raise LegendError('Repeated annotation identity in registration.')
    return data


def legend_settings(registry):
    """(categories, excluded) of a validated registry; format 1 = Casework, nothing excluded."""
    if registry.get('version') == LEGACY_LEGEND_FORMAT:
        return list(DEFAULT_CATEGORIES), []
    return list(registry['categories']), list(registry['excluded'])


def with_settings(registry, categories, excluded):
    """Copy written in the SAME transaction as the rows, so settings and legend commit or roll back together."""
    updated = dict(registry)
    updated.update(version=LEGEND_FORMAT, categories=list(validate_categories(list(categories))),
                   excluded=sorted(set(excluded)))
    return updated


def initial_selection(scanned_uids, registry_rows, excluded):
    """Checkbox state per scanned material: excluded stays unchecked, everything else checked.
    'new' = neither shown in the legend before nor excluded before."""
    excluded = set(excluded)
    return dict((uid, {'checked': uid not in excluded,
                       'new': uid not in registry_rows and uid not in excluded})
                for uid in scanned_uids)


def apply_selection(scanned_uids, excluded, checked_uids):
    """Unchecked scanned materials become excluded, checked ones are re-included, and
    exclusions of materials absent from this scan are kept (they stay excluded on return)."""
    scanned = set(scanned_uids)
    checked = set(checked_uids)
    if not checked.issubset(scanned):
        raise LegendError('Selection contains materials that were not scanned.')
    return sorted((set(excluded) - scanned) | (scanned - checked))


def legend_rows(scanned_rows, excluded):
    excluded = set(excluded)
    return [row for row in scanned_rows if row['uid'] not in excluded]


def new_rows(rows, registry_rows):
    return [row for row in rows if row['uid'] not in registry_rows]


def validate_row(data, registry, material_uid, role, actual_view_uid):
    validate_stamp(data, 'row')
    expected = {'source': registry['source'], 'legend': registry['legend'],
                'material': material_uid, 'role': role}
    if actual_view_uid != registry['source'] or any(data.get(k) != v for k, v in expected.items()):
        raise LegendError('Annotation ownership/View mismatch; no changes made.')


def atomic(adapter, action):
    """A legend is one atomic unit; the adapter owns transaction status checks."""
    adapter.start()
    try:
        result = action()
        adapter.commit()
        return result
    except Exception:
        original_traceback = traceback.format_exc()
        try:
            adapter.rollback()
        except Exception as rollback_error:
            rollback_error.original_traceback = original_traceback
            raise
        raise
