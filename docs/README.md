# Gyminators documentation

Use the guide that matches the job you are doing.

| Document | Audience | Use it for |
| --- | --- | --- |
| [Administrator guide](ADMIN_GUIDE.md) | Owner and website managers | Logging in, editing pages, managing pictures and links, controlling the public waiver, reviewing waiver records, publishing changes, and managing website users |
| [Owner approval checklist](OWNER_CHECKLIST.md) | Owner and launch lead | Jackrabbit configuration, the approved waiver baseline, privacy and retention policies, credentials, security, content approval, and launch readiness |
| [Content audit](CONTENT_AUDIT.md) | Owner and content editor | Checking which claims came from the existing site and which time-sensitive details still require approval |
| [Jackrabbit Zapier setup](JACKRABBIT_ZAPIER_SETUP.md) | Owner and technical administrator | Connecting the nine approved non-financial event feeds, backfilling history, testing, and rotating the inbound token |
| [Project README](../README.md) | Developer or hosting administrator | Local setup, deployment, roles, architecture, backups, restore, and verification commands |

## System boundaries

- Django runs the public marketing website, content-management screens, online
  waiver workflow, limited operational reporting dashboard, and cached public
  class reporting.
- Jackrabbit owns registration, class availability and tuition, family accounts,
  payments, refunds, and authoritative business reporting.
- The reporting ledger contains only approved opaque Jackrabbit identifiers and
  timestamps; it does not receive names, contact details, birthdates, balances,
  payment records, or raw Zapier payloads. Separately, the waiver feature does
  store minor and guardian identity/contact details, birthdates, emergency and
  medical information, immutable agreement snapshots, and private signatures.
- Waiver signatures are stored privately in the database, not under `/media`.
  Each signed waiver also stores one validated, immutable PDF artifact in the
  database. Authorized downloads return its exact bytes; PDFs are not
  regenerated and neither signatures nor PDFs have public media URLs.
- The Django **Website Admin Login** and all Jackrabbit logins are separate
  accounts. Never reuse passwords between them.
- Uploaded website images and the Django database must be backed up together.
  The database backup includes the limited operational ledger, cached public
  classes, full waiver records, signatures, and stored signed PDFs. Treat
  database backups as highly sensitive, encrypt off-site copies, and restrict
  access. Complete Jackrabbit records must still be protected, retained, and
  exported separately under the owner's approved procedures.

## Keeping documentation current

Update the administrator guide whenever an editing screen or role changes.
Update the owner checklist when a launch decision is completed or a new policy
is required. The exact current Regular and Camp wording is legally approved and
must remain unchanged. Any agreement text or version change requires renewed
legal review before release, a new version, and corresponding documentation and
test updates. Waiver privacy, consent, retention, or access-control changes also
require the appropriate owner/legal review. Re-run the content audit before
launch and whenever the source site or Jackrabbit organization links change.
