"""Sign-in and missing deployment configuration checks without a network."""
from pathlib import Path
import sys
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
source = (Path(__file__).resolve().parents[1] / 'ledger_web.py').read_text(encoding='utf-8')
prefix = source.split('if not check_password():', 1)[0]
login = prefix + '\nif check_password():\n    st.success("Authorized")\n'
with patch('mysql.connector.connect') as connect:
    for configured, supplied, accepted in [(None, '', False), ('synthetic-only', 'wrong', False), ('synthetic-only', 'synthetic-only', True)]:
        app = AppTest.from_string(login, default_timeout=20)
        app.secrets['test_marker'] = True
        if configured is not None:
            app.secrets['app_password'] = configured
        app.run()
        app.text_input[0].set_value(supplied)
        app.button[0].click().run()
        assert not app.exception, app.exception
        assert any(item.value == 'Authorized' for item in app.success) == accepted
    # Authenticated path with no mysql table or with missing CA must stop safely.
    for mysql_config in [None, dict(host='test', user='test', password='test', database='test')]:
        app = AppTest.from_string(source.replace('if not check_password():', 'if False:'), default_timeout=20)
        app.secrets['test_marker'] = True
        if mysql_config is not None:
            app.secrets['mysql'] = mysql_config
        app.run()
        assert not app.exception, app.exception
        assert any('Database unavailable' in item.value for item in app.error)
    connect.assert_not_called()
print('PASS: missing/wrong/correct sign-in and missing mysql/CA denial without database access')
