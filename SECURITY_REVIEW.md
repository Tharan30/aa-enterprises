# Security review and deployment checklist

Reviewed source snapshot: 1ac1f5105355e82064ee14b89bb7088360f72bb6.

## Immediate action
Critical: gsync_auth.py contained a reversible encoded Google service-account private key. Revoke that key in Google Cloud and issue a replacement. Deleting source does not revoke credentials or remove history. Audit service-account usage and restrict access to the intended spreadsheet.
High: Petrolbunk.py contained a database password. Rotate it and review database access logs. Supply AA_DB_HOST, AA_DB_USER, AA_DB_PASSWORD and AA_DB_NAME through the desktop process environment.

## Changes
- Load Google credentials from Streamlit's gcp_service_account secret table; google_sheet_id must be explicitly configured. Drive-wide scope removed.
- Remove the default yearly cleanup password; missing configuration denies cleanup.
- Write Sheets values as RAW to prevent spreadsheet formula interpretation.
- Hide database connection and Sheets exception details from users.
- Escape customer names in the HTML balance banner.
- Responsive summary cards, mobile form stacking, keyboard focus indicators, compact sign-in, and consistent touch targets.
- Accept only the documented XLSX import format.

## Remaining risks
- Authentication is a shared password with session-local throttling; a new session bypasses the counter. Deploy behind an identity-aware gateway with persistent throttling. There are no individual roles or audit identities; every authenticated operator can modify and delete customer data.
- MySQL TLS certificate/hostname validation is not explicitly enforced. Configure verified TLS appropriate to the database deployment.
- MySQL and Sheets updates are not atomic; retries can duplicate or miss synchronization. Use a transactional outbox and immutable transaction IDs before treating Sheets as an audit trail.
- Worksheet titles truncate customer names and can collide. Migrate to stable customer-ID based identifiers with an explicit mapping.
- Requirements are unpinned. Generate a tested lockfile and run a vulnerability audit in CI; no advisory scan was completed here.
- Financial calculations use floating point; migrate consistently to Decimal and database DECIMAL with reconciliation tests.
- Imports need decompressed XLSX size limits and transaction rollback verification. Some operation errors still show raw exception text.
- Desktop application relies on database authorization and has no application login.

## Validation and rollout
Python compilation checks only; production database and Google Sheets were not accessed. No browser or integration validation was possible in this environment. Before deployment, configure replacement secrets, verify sign-in and missing-secret behavior, exercise customer/transaction CRUD against a disposable database, check XLSX and Sheets formula handling, and verify desktop/tablet/mobile layouts. Back up data and test recovery before enabling yearly clearance.
