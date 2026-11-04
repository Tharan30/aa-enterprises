"""Start a private, temporary MySQL server; use synthetic data only.

Usage: python tests/check_disposable_mysql.py --mysqld /path/to/mysqld
No existing server configuration, environment credentials, or app startup is used.
"""
import argparse
import ast
from decimal import Decimal
from pathlib import Path
import socket
import subprocess
import tempfile
import time

import mysql.connector
from check_security import application_functions


def validate(connection):
    cursor = connection.cursor(buffered=True)
    cursor.execute('CREATE DATABASE aa_disposable_validation')
    cursor.execute('USE aa_disposable_validation')
    source = (Path(__file__).resolve().parents[1] / 'Petrolbunk.py').read_text(encoding='utf-8')
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lstrip().startswith('CREATE TABLE IF NOT EXISTS'):
            cursor.execute(node.value)
    cursor.execute("INSERT INTO sales VALUES (1, 'Synthetic')")
    cursor.execute("INSERT INTO customers VALUES (1, 1, 'Same', '111'), (2, 1, 'Same', '222')")
    connection.commit()
    functions = application_functions()
    recalculate = functions['recalculate_balances']
    insert = '''INSERT INTO ledger_transactions
        (customer_id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance)
        VALUES (1, %s, %s, 'TEST', 'Diesel', 0, %s, %s, 0)'''
    cursor.executemany(insert, [('2025-02-02', 'SALE', '100.10', '0'), ('2025-01-01', '=literal', '0', '20.05')])
    recalculate(connection, 1)
    connection.commit()
    cursor.execute('SELECT balance FROM ledger_transactions ORDER BY trans_date, id')
    assert cursor.fetchall() == [(Decimal('-20.05'),), (Decimal('80.05'),)]
    # Inject a server-side error after the INSERT but during balance recalculation.
    cursor.execute("CREATE TRIGGER reject_balance BEFORE UPDATE ON ledger_transactions FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Synthetic failure'")
    try:
        cursor.execute(insert, ('2025-03-01', 'ROLLBACK', '1', '0'))
        recalculate(connection, 1)
    except mysql.connector.Error:
        connection.rollback()
    else:
        raise AssertionError('Injected failure was not raised')
    cursor.execute('SELECT COUNT(*) FROM ledger_transactions')
    assert cursor.fetchone() == (2,)
    cursor.execute('DROP TRIGGER reject_balance')
    cursor.execute("DELETE FROM ledger_transactions WHERE trans_id='SALE'")
    recalculate(connection, 1)
    connection.commit()
    cursor.execute('SELECT balance FROM ledger_transactions')
    assert cursor.fetchall() == [(Decimal('-20.05'),)]
    assert not functions['archive_old_year_transactions'](connection, 2025)[0]
    cursor.execute('DELETE FROM customers WHERE customer_id=1')
    connection.commit()
    cursor.execute('SELECT COUNT(*) FROM ledger_transactions')
    assert cursor.fetchone() == (0,)
    cursor.execute('SELECT COUNT(*) FROM customers')
    assert cursor.fetchone() == (1,)
    cursor.close()
    print('PASS: synthetic schema, duplicate names, backdated balances, injected rollback, deletion/cascade, clearance denial')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mysqld', required=True)
    args = parser.parse_args()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    # No recursive cleanup: leave the isolated data/logs for inspection.
    directory = Path(tempfile.mkdtemp(prefix='aa-disposable-', dir=Path(__file__).resolve().parents[1].parent))
    data = directory / 'data'
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    with (directory / 'mysql.log').open('w') as log:
        subprocess.run([args.mysqld, '--no-defaults', '--initialize-insecure', f'--datadir={data}', '--console'], stdout=log, stderr=log, check=True, timeout=60, creationflags=flags)
        server = subprocess.Popen([args.mysqld, '--no-defaults', f'--datadir={data}', '--bind-address=127.0.0.1', f'--port={port}', '--mysqlx=OFF', '--skip-log-bin', '--console'], stdout=log, stderr=log, creationflags=flags)
        connection = None
        try:
            deadline = time.monotonic() + 30
            while connection is None and time.monotonic() < deadline:
                try:
                    connection = mysql.connector.connect(host='127.0.0.1', port=port, user='root', password='', ssl_disabled=True, connection_timeout=1)
                except mysql.connector.Error:
                    if server.poll() is not None:
                        raise RuntimeError(f'Temporary server exited; inspect {directory}')
                    time.sleep(0.25)
            if connection is None:
                raise RuntimeError(f'Temporary server did not start; inspect {directory}')
            validate(connection)
        finally:
            if connection is not None:
                try:
                    connection.cmd_shutdown()
                except mysql.connector.Error:
                    pass
                connection.close()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.terminate()
                server.wait(timeout=10)
    print(f'Temporary server stopped; synthetic files retained at {directory}')


if __name__ == '__main__':
    main()
