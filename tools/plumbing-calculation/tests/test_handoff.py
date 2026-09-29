from __future__ import unicode_literals
import base64
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(HERE, '..', 'YSU Tools.extension', 'YSU Tools.tab', 'Planning.panel', 'Plumbing Calculation.pushbutton')
sys.path.insert(0, BUNDLE)
from handoff import make_payload, encode_url, MAX_URL_LENGTH, CANONICAL_URL


class HandoffTests(unittest.TestCase):
    def fixture(self):
        with open(os.path.join(HERE, 'revit_shyfc.json')) as stream:
            return json.load(stream)

    def test_golden_round_trip(self):
        value = self.fixture()
        url = encode_url(value)
        encoded = url.split('#revit=')[1]
        decoded = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8'))
        self.assertEqual(value, decoded)
        self.assertLessEqual(len(url), MAX_URL_LENGTH)
        self.assertNotIn('=', encoded)
        print('Golden URL characters: {0}; UTF-8 JSON bytes: {1}'.format(len(url), len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8'))))

    def test_unicode_blank_numeric_strings(self):
        value = make_payload('Project', '\u7d66\u6392\u6c34', 1, ['Name', 'Value'], [['\u6559\u5ba4', '001.20'], ['', '']])
        url = encode_url(value)
        token = url.split('#revit=')[1]
        self.assertEqual(json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)).decode('utf-8')), value)

    def test_invalid_tables(self):
        for rows in [[], [['']], [['X', 1]], [['X']], 'bad']:
            with self.assertRaises(ValueError):
                make_payload('Project', 'Schedule', 1, ['Name', 'Value'], rows)
        with self.assertRaises(ValueError):
            make_payload('Project', 'Schedule', True, ['X'], [['1']])

    def test_size_guard_no_truncation(self):
        value = make_payload('Project', 'Schedule', 1, ['X'], [['Z' * 2000]])
        with self.assertRaises(ValueError):
            encode_url(value)
        self.assertEqual(len(value['rows'][0][0]), 2000)

    def test_schema_and_immutability(self):
        value = self.fixture()
        snapshot = json.dumps(value)
        encode_url(value)
        self.assertEqual(json.dumps(value), snapshot)
        value['schemaVersion'] = 2
        with self.assertRaises(ValueError):
            encode_url(value)


if __name__ == '__main__':
    unittest.main()
