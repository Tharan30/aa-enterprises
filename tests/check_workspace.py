from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
from streamlit.testing.v1 import AppTest

source = (Path(__file__).resolve().parents[1] / 'ledger_web.py').read_text(encoding='utf-8')
source = source.replace('if not check_password():', 'if False:')
customers = pd.DataFrame([(1, 'Acme', '123'), (2, 'Acme', '456')], columns=['customer_id', 'customer_name', 'phone'])
transactions = pd.DataFrame([(1, date.today(), 'SALE-1', 'TN01', 'Diesel', 10, 1000, 0, 1000)], columns=['id', 'trans_date', 'trans_id', 'vehicle', 'product', 'litres', 'debit', 'credit', 'balance'])

def read_sql(query, connection, params=None):
    return customers.copy() if 'FROM customers' in query else transactions.copy()

connection = MagicMock()
def execute(query, params=None):
    connection.cursor.return_value.fetchone.return_value = (1000, 0) if 'SUM(' in query else (1,)
connection.cursor.return_value.execute.side_effect = execute
with patch('mysql.connector.connect', return_value=connection), patch('pandas.read_sql', side_effect=read_sql):
    app = AppTest.from_string(source, default_timeout=20)
    app.secrets['mysql'] = dict(host='test', port=3306, user='test', password='test', database='test', ssl_ca='test-ca.pem')
    app.run()
    assert not app.exception, app.exception
    assert app.radio(key='workspace').value == 'Ledger'
    assert len(app.selectbox(key='ledger_customer').options) == 2
    for section in ['Customers', 'Import', 'Manage', 'Ledger']:
        app.radio(key='workspace').set_value(section).run()
        assert not app.exception, app.exception
        if section == 'Customers':
            next(item for item in app.text_input if item.label == 'Search customers').set_value('no match').run()
            assert any('No matching' in item.value for item in app.info)
        if section == 'Manage':
            assert app.button(key='btn_del_cust').disabled
            assert app.button(key='btn_del_trans').disabled
            assert app.button(key='btn_run_archive').disabled
    print('PASS: four workspaces, duplicate customer selection, search empty state, deletion guards')
