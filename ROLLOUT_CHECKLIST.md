# Ordered rotation and disposable validation checklist

Run commands from the repository root in PowerShell unless marked SQL. Replace placeholders privately; never put secrets/production records in Git, PRs, logs or this chat. Do not launch either app against production for validation.

1. **Contain/revoke — cloud owner.** Pause rollout and restrict access. Identify the exposed key through private incident records and the service-account Keys page; do not decode historical source here. Delete it immediately, then confirm it is absent:

   ```powershell
   gcloud iam service-accounts keys list --iam-account='<SERVICE_ACCOUNT_EMAIL>' --managed-by=user --project='<PROJECT_ID>'
   gcloud iam service-accounts keys delete '<EXPOSED_KEY_ID>' --iam-account='<SERVICE_ACCOUNT_EMAIL>' --project='<PROJECT_ID>'
   gcloud iam service-accounts keys list --iam-account='<SERVICE_ACCOUNT_EMAIL>' --managed-by=user --project='<PROJECT_ID>'
   ```

   Audit service-account activity, IAM roles and spreadsheet sharing. If this app still needs a JSON key, create its replacement outside the checkout, in an approved private location:

   ```powershell
   gcloud iam service-accounts keys create '<PRIVATE_ABSOLUTE_PATH>/replacement.json' --iam-account='<SERVICE_ACCOUNT_EMAIL>' --project='<PROJECT_ID>'
   ```

   Share only intended spreadsheets with the service account. Narrow OAuth scope does not revoke existing IAM/Drive permissions. Coordinate history cleanup/old-clone retirement after revocation; history cleanup alone never clears this gate.

2. **Rotate MySQL — DBA.** Use a private verified-TLS administrator session (`-p` prompts):

   ```powershell
   mysql --host='<CERTIFICATE_MATCHING_DB_HOST>' --port=3306 --user='<DB_ADMIN>' -p --ssl-mode=VERIFY_IDENTITY --ssl-ca='<PRIVATE_CA_PATH>'
   ```

   Confirm the actual account host part from grants; do not assume `%`. MySQL 8 SQL:

   ```sql
   SHOW GRANTS FOR 'ledger_user'@'<EXACT_ACCOUNT_HOST>';
   ALTER USER 'ledger_user'@'<EXACT_ACCOUNT_HOST>' IDENTIFIED BY RANDOM PASSWORD;
   ALTER USER 'ledger_user'@'<EXACT_ACCOUNT_HOST>' REQUIRE SSL;
   ```

   Capture the generated password directly into the secret store. Update every consumer, restart clients and terminate old authenticated sessions. Prove old-password rejection on a NEW connection and replacement success. Review DB access logs/network grants. Web needs SELECT/INSERT/UPDATE/DELETE on its schema; desktop currently also runs CREATE/ALTER at startup, requiring a separately reviewed schema-bootstrap/desktop privilege plan.

3. **Configure replacement secrets and access controls — deployment owner.** Use the Streamlit deployment secrets UI or ignored `.streamlit/secrets.toml`. Top-level keys precede tables:

   ```toml
   app_password = "<NEW_UNIQUE_SHARED_PASSWORD>"
   google_sheet_id = "<SANDBOX_SHEET_ID>"
   # yearly_cleanup_password: leave unset; clearance is disabled in code.

   [mysql]
   host = "<CERTIFICATE_MATCHING_DB_HOST>"
   port = 3306
   user = "<RESTRICTED_ACCOUNT>"
   password = "<ROTATED_PASSWORD>"
   database = "<DISPOSABLE_DATABASE>"
   ssl_disabled = false
   ssl_ca = "<PRIVATE_ABSOLUTE_CA_PATH>"

   [gcp_service_account]
   type = "service_account"
   project_id = "<PROJECT_ID>"
   private_key_id = "<REPLACEMENT_KEY_ID>"
   private_key = """<REPLACEMENT_PEM_WITH_REAL_NEWLINES>"""
   client_email = "<SERVICE_ACCOUNT_EMAIL>"
   client_id = "<CLIENT_ID>"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "<VALUE_FROM_REPLACEMENT_JSON>"
   ```

   Copy issued JSON fields privately, including any additional fields. Desktop environment names: **AA_DB_HOST, AA_DB_PORT** (optional, default 3306), **AA_DB_USER, AA_DB_PASSWORD, AA_DB_NAME, AA_DB_SSL_CA**. Both clients enforce certificate and hostname verification; web verification flags cannot be independently disabled. Set the identity-aware gateway and persistent throttling before network access. Test missing/wrong `app_password`, missing DB secrets/CA, absent Sheets credentials, unauthorized users and fresh-session guessing without exposing exception details.

4. **Run repository checks — no credentials, Python 3.11:**

   ```powershell
   python -m venv .venv
   .venv/Scripts/python -m pip install -r requirements.lock
   .venv/Scripts/python -m pip check
   .venv/Scripts/python -m py_compile ledger_web.py Petrolbunk.py ledger_security.py
   .venv/Scripts/python tests/check_security.py
   .venv/Scripts/python tests/check_auth.py
   .venv/Scripts/python tests/check_workspace.py
   .venv/Scripts/python -m pip_audit -r requirements.lock
   .venv/Scripts/python tests/check_disposable_mysql.py --mysqld 'C:/Program Files/MySQL/MySQL Server 8.0/bin/mysqld.exe'
   ```

   Last command initializes its OWN temporary datadir, ignores installed MySQL defaults, chooses a loopback port, creates synthetic schema/data and shuts down its server. It never uses `AA_DB_*`/Streamlit secrets, and retains synthetic data/logs beside the checkout. It tests SQL/helpers, not full UI/TLS. Use a MySQL 8 executable on other platforms. Do not substitute an existing server/production dump. The lock includes audit tooling and was resolved on Windows/Python 3.11; rerun checks on the deployment platform. Desktop GUI dependencies (`customtkinter`, `tkcalendar`, `reportlab`) are a separate unvalidated installation scope.

5. **Disposable end-to-end acceptance — owner and engineering.** Provision a separate synthetic InnoDB schema from reviewed desktop DDL; do not use desktop startup as a production migration. For local web-only unencrypted testing, use `mysql.host="127.0.0.1"`, disposable port and `mysql.ssl_disabled=true`; never use this for a remote server. Start:

   ```powershell
   .venv/Scripts/python -m streamlit run ledger_web.py --server.address=127.0.0.1
   ```

   Check customer/transaction CRUD; duplicate/truncated/colliding names; backdated/same-day sales/payments and exact balances; concurrent writes; invalid dates/nonfinite/negative/oversized amounts; schema lengths; 5,000/5,001 rows and malformed/expanded XLSX limits; insertion/recalculation failure rollback; formula-like `=`, `+`, `-`, `@` fields through XLSX export and sandbox Sheets RAW writes. Imports must warn sync is pending; cleanup must stay disabled even with `yearly_cleanup_password` set. Invalid/missing financial inputs currently coerce to defaults: define a contract and fix/retest before rollout.

   In a separate sandbox Sheet, test outage/retry/duplicate handling, chronological balances and wrong-customer deletion. These expose unresolved ID/outbox issues; a successful append alone does not clear the gate. Test correct CA/hostname success, wrong CA/hostname rejection, gateway identities/throttling and desktop separately. Record expected vs observed values; do not reconnect these tests to production.

6. **Recovery/release decision — owner and DBA.** Back up through the approved private process, restore into an isolated environment and reconcile customer counts, immutable transaction IDs/counts and balances. Do not copy production data into these local tests. Record rotation, access/TLS, reconciliation, target-platform audit, recovery and UI evidence privately. Keep PR draft/unmerged until applicable blockers in `SECURITY_REVIEW.md` are cleared. Re-enabling yearly clearance requires a new reviewed design with verified ID-based archive, atomic pruning, idempotency and tested recovery; setting a password cannot enable it.

References: [Google key lifecycle](https://docs.cloud.google.com/iam/docs/keys-create-delete), [MySQL Connector/Python TLS arguments](https://dev.mysql.com/doc/connectors/en/connector-python-connectargs.html), [MySQL account rotation syntax](https://dev.mysql.com/doc/refman/8.0/en/alter-user.html).
