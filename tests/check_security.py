"""Offline guards; never import the application or connect to a database."""
import ast
from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ledger_security import mysql_options, validate_xlsx


def application_functions():
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'ledger_web.py').read_text(encoding='utf-8'))
    names = {'run_query', 'recalculate_balances', 'archive_old_year_transactions'}
    namespace = {}
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[]), 'ledger_functions', 'exec'), namespace)
    return namespace


class SecurityTests(unittest.TestCase):
    def test_tls_fails_closed(self):
        config = dict(host='db.example.invalid', user='test', password='test', database='test')
        with self.assertRaises(KeyError):
            mysql_options(config)
        with self.assertRaises(ValueError):
            mysql_options(dict(config, ssl_disabled=True))
        options = mysql_options(dict(config, ssl_ca='ca.pem'))
        self.assertTrue(options['ssl_verify_cert'] and options['ssl_verify_identity'])
        self.assertTrue(mysql_options(dict(config, host='127.0.0.1', ssl_disabled=True))['ssl_disabled'])

    def test_xlsx_expansion_limit(self):
        upload = BytesIO()
        with ZipFile(upload, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', '')
            archive.writestr('xl/workbook.xml', b'x' * (26 * 1024 * 1024))
        with self.assertRaises(ValueError):
            validate_xlsx(upload)
        self.assertEqual(upload.tell(), 0)

    def test_valid_xlsx(self):
        from openpyxl import Workbook
        upload = BytesIO()
        Workbook().save(upload)
        validate_xlsx(upload)
        self.assertEqual(upload.tell(), 0)

    def test_clearance_cannot_touch_database(self):
        connection = MagicMock()
        ok, message = application_functions()['archive_old_year_transactions'](connection, 2025)
        self.assertFalse(ok)
        self.assertIn('disabled', message)
        self.assertEqual(connection.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
