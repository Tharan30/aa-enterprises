# Security review and rollout gates

Re-reviewed PR #1 at `431baffb4c3ba31620e998a7cb55d34b3d3f6fb3`, plus this follow-up. Original exposed snapshot: `1ac1f5105355e82064ee14b89bb7088360f72bb6`. No live credentials, production database, or Google Sheet were accessed. PR remains a draft; this is not deployment approval.

## Remaining blockers, in order

1. **Compromised credentials:** the encoded Google service-account private key and desktop MySQL password remain in Git history. Owner must revoke the Google key, rotate the actual MySQL account/password, terminate old authenticated sessions, update every deployment, and audit access. Revocation is unverified; source deletion is not revocation.
2. **Access control:** shared `app_password` and session-local throttling permit cross-session guessing; operators share full write/delete access. Require an identity-aware gateway, persistent throttling, and an explicit operator permissions/audit-identity decision. Desktop has no application login: restrict OS and DB access to authorized operators.
3. **Verified TLS configuration:** both clients now require `mysql.ssl_ca` / `AA_DB_SSL_CA` and enforce certificate AND hostname verification. Only explicit web loopback testing permits `mysql.ssl_disabled=true`. Supply a trusted CA, matching hostname and restricted DB grants; prove wrong-CA/wrong-host rejection. Existing deployments without a CA will fail closed.
4. **Sheets correctness:** sanitized/truncated customer-name tabs collide, sync/deletion match nonunique business fields, and there is no transactional outbox. Backdated inserts append the final ledger balance rather than that row's chronological balance. Import auto-append is suspended because selecting the last N chronological rows could append unrelated records. Before treating Sheets as a reliable mirror/audit trail: implement stable customer/transaction DB-ID mapping, an idempotent outbox/retry/reconciliation flow, and a reviewed migration of existing tabs. Do not repair this by re-importing data.
5. **Financial/schema correctness:** code converts database DECIMAL to float, and concurrent writers are not serialized per customer. Reconcile rounding and concurrent mutations before financial rollout. Web accepts vehicle/product lengths 50/100 while desktop DDL uses VARCHAR(20)/VARCHAR(50). Import defaults invalid/missing dates to today, invalid amounts to zero and clips negatives. Define/test the accepted schema and reject ambiguous financial inputs. Do not silently migrate production columns/data.
6. **Deployment acceptance:** complete target-platform dependency checks, gateway/TLS tests, synthetic end-to-end UI/import/export and sandbox Sheets tests, and isolated backup restore/reconciliation. Local tests do not establish these. Keep yearly clearance disabled.

## Safe follow-up changes

- Removed annual deletion implementation and disabled its UI. Previously, Sheets failures were swallowed and deletion committed before replacement balances; rollback could not recover lost history. No configuration switch re-enables clearance. `yearly_cleanup_password` is now unused/reserved; leave unset.
- Web mutation plus running-balance recalculation now share one MySQL commit for add/import/delete (requires transactional/InnoDB tables). This does not solve concurrent-writer races or cross-system atomicity.
- Added XLSX compressed (5 MiB), expanded archive (25 MiB), entry-count (1,000), and parsed-row (5,001 sentinel / 5,000 accepted) limits. Read/import errors no longer expose exception text.
- Removed incorrect import sync and success claims; successful imports report MySQL save plus pending Sheets reconciliation.
- Added verified TLS configuration, offline security tests and an isolated MySQL regression runner. Pinned web dependencies and recorded a full validation environment lock, including audit tooling; CI runs without secrets.

## Validation evidence and limits

On 2026-11-04, Python 3.11 / Windows: compilation, pip check, four offline security tests, missing/wrong/correct sign-in and missing MySQL/CA denial checks, and AppTest for four workspaces/duplicate-name selection/search/deletion and clearance guards passed. A fresh environment from pinned dependencies passed these checks. `pip-audit -r requirements.lock` reported **no known vulnerabilities**; this is advisory coverage at scan time, not proof of absence.

The disposable MySQL 8.0.40 runner passed synthetic schema/duplicate names/backdated balance checks, injected-update-failure rollback, transaction deletion/customer cascade and clearance denial. It starts its own loopback server, ignores installed defaults, never reads application secrets, stops its process and retains synthetic files. It tests SQL/helpers, not full import/desktop UI or TLS. The desktop application is not imported because startup performs DDL.

Prior PR body reports desktop/mobile browser checks; these were not repeated here. The original review's compilation-only statement was stale. No production/Google integration, deployment-platform CI result, credential revocation, or backup recovery is attested. See `ROLLOUT_CHECKLIST.md` for exact commands and owner actions.
