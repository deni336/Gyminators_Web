# Gyminators documentation

Use the guide that matches the job you are doing.

| Document | Audience | Use it for |
| --- | --- | --- |
| [Administrator guide](ADMIN_GUIDE.md) | Owner and website managers | Logging in, editing pages, managing pictures and links, publishing changes, and managing website users |
| [Owner approval checklist](OWNER_CHECKLIST.md) | Owner and launch lead | Jackrabbit configuration, policies, credentials, security, content approval, and launch readiness |
| [Content audit](CONTENT_AUDIT.md) | Owner and content editor | Checking which claims came from the existing site and which time-sensitive details still require approval |
| [Jackrabbit Zapier setup](JACKRABBIT_ZAPIER_SETUP.md) | Owner and technical administrator | Connecting the nine approved non-financial event feeds, backfilling history, testing, and rotating the inbound token |
| [Project README](../README.md) | Developer or hosting administrator | Local setup, deployment, roles, architecture, backups, restore, and verification commands |

## System boundaries

- Django runs the public marketing website, content-management screens, limited
  operational reporting dashboard, and cached public class reporting.
- Jackrabbit owns registration, class availability and tuition, family accounts,
  payments, refunds, and authoritative business reporting.
- Django stores a privacy-minimized reporting ledger containing approved opaque
  Jackrabbit identifiers and timestamps. It does not store names, contact
  details, birthdates, balances, payment records, or raw Zapier payloads.
- The Django **Website Admin Login** and all Jackrabbit logins are separate
  accounts. Never reuse passwords between them.
- Uploaded website images and the Django database must be backed up together.
  The database backup includes the limited operational ledger and cached public
  classes. Complete Jackrabbit records must still be protected, retained, and
  exported separately under the owner's approved procedures.

## Keeping documentation current

Update the administrator guide whenever an editing screen or role changes.
Update the owner checklist when a launch decision is completed or a new policy
is required. Re-run the content audit before launch and whenever the source site
or Jackrabbit organization links change.
