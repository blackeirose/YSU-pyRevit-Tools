# -*- coding: utf-8 -*-
"""Pure Python 2.7/3 compatible transport; no Revit or calculation code."""
from __future__ import unicode_literals
import base64
import json

CANONICAL_URL = 'https://tools.ycsu.cc/plumbing-chart/'
MAX_URL_LENGTH = 2000
try:
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)


def make_payload(document_title, schedule_name, schedule_id, columns, rows):
    if not isinstance(document_title, string_types) or not isinstance(schedule_name, string_types) or not schedule_name.strip():
        raise ValueError('Invalid schedule identity.')
    if isinstance(schedule_id, bool) or not isinstance(schedule_id, integer_types) or not 0 < schedule_id <= 9007199254740991:
        raise ValueError('Invalid schedule ID.')
    if not isinstance(columns, list) or not 0 < len(columns) <= 64 or any(not isinstance(c, string_types) for c in columns):
        raise ValueError('Invalid displayed columns.')
    if not isinstance(rows, list) or not 0 < len(rows) <= 500:
        raise ValueError('The schedule is empty or too large.')
    if any(not isinstance(row, list) or len(row) != len(columns) or any(not isinstance(c, string_types) for c in row) for row in rows):
        raise ValueError('The displayed table is malformed.')
    if not any(c.strip() for row in rows for c in row):
        raise ValueError('The schedule is empty.')
    return {'schemaVersion': 1, 'source': 'revit-schedule', 'documentTitle': document_title,
            'scheduleName': schedule_name, 'scheduleId': schedule_id,
            'columns': [{'index': i, 'name': c} for i, c in enumerate(columns)],
            'rows': [list(row) for row in rows]}


def encode_url(payload):
    if not isinstance(payload, dict) or payload.get('schemaVersion') != 1 or payload.get('source') != 'revit-schedule':
        raise ValueError('Unsupported handoff schema.')
    cols = payload.get('columns', [])
    if not isinstance(cols, list):
        raise ValueError('Invalid columns.')
    if any(not isinstance(c, dict) or c.get('index') != i for i, c in enumerate(cols)):
        raise ValueError('Invalid column indexes.')
    validated = make_payload(payload.get('documentTitle'), payload.get('scheduleName'), payload.get('scheduleId'),
                             [c.get('name') for c in cols], payload.get('rows'))
    data = json.dumps(validated, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')
    encoded = base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')
    url = CANONICAL_URL + '#revit=' + encoded
    if len(url) > MAX_URL_LENGTH:
        raise ValueError('Schedule handoff needs {0} URL characters; V1 allows {1}. Nothing was truncated. Use the existing Web PDF/Image workflow instead.'.format(len(url), MAX_URL_LENGTH))
    return url
