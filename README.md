# Gyminators Gymnastics

A server-rendered Django marketing website with owner-managed content,
non-financial Jackrabbit activity reporting, a cached public class feed,
PostgreSQL, and a production Docker deployment.

## Documentation

- [Administrator guide](docs/ADMIN_GUIDE.md) — everyday website editing and user management
- [Owner launch checklist](docs/OWNER_CHECKLIST.md) — business, Jackrabbit, security, and launch decisions
- [Live-site content audit](docs/CONTENT_AUDIT.md) — verified source content and deliberate exclusions
- [Documentation index](docs/README.md) — which guide to use for each job
- [Jackrabbit Zapier setup](docs/JACKRABBIT_ZAPIER_SETUP.md) — activate the nine approved operational event feeds

## Local development

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe .\run.py
```

`run.py` applies migrations, creates/updates the manager roles, starts Django,
and opens the website in your browser. On the first run, create the owner login
in a second terminal with
`& .\.venv\Scripts\python.exe manage.py createsuperuser`, or stop the server
and use `& .\.venv\Scripts\python.exe .\run.py --create-admin`. Run
`& .\.venv\Scripts\python.exe .\run.py --help` for host, port, browser, and
migration options. Using the explicit `.venv` interpreter avoids relying on a
stale VS Code or PowerShell interpreter selection.

For safety, the launcher ignores inherited `DB_HOST` and related settings and
uses local SQLite. A developer who intentionally wants the environment-defined
database must add `--use-environment-database`.

`run.py --host 0.0.0.0` exposes Django's DEBUG development server to the local
network. Use it only on a trusted network for short-lived testing; it is never a
production deployment method.

Open:

- Website: `http://localhost:8000`
- Website dashboard: `http://localhost:8000/dashboard/`
- Website administrator login: `http://localhost:8000/staff/login/`
- Website management: `http://localhost:8000/dashboard/content/`
- Business activity reports: `http://localhost:8000/dashboard/reporting/`
- Cached class reporting: `http://localhost:8000/dashboard/reporting/classes/`
- Django admin: `http://localhost:8000/django-admin/`

Local development uses SQLite at `data/gyminators-django.db`. No Node.js build
or frontend server is required. Administrator accounts are stored in that local
database and are not copied automatically into production PostgreSQL.

## Staff roles and access

After every new installation, and after deployments that add permissions, run:

```powershell
& .\.venv\Scripts\python.exe manage.py setup_roles
```

In Docker, use `docker compose exec app python manage.py setup_roles`. The
command idempotently creates and resets three application-owned groups:

- **Website Managers** can edit business details, homepage content, pictures,
  programs, events, highlights, social links, and the public Jackrabbit links.
- **Business Managers** is retained only for existing account assignments and
  currently has the same website-content permissions. Assign new content users
  to **Website Managers**.
- **Reporting Managers** can view the limited operational dashboard and cached
  public class data. It cannot edit website content, browse raw imported records,
  or access Jackrabbit. Assign it only to staff approved for business activity
  reporting. Raw diagnostics and class-feed refresh controls remain
  superuser-only.

Use the superuser account to assign each staff account to the appropriate group
under **Django admin > Users**. Group membership permits the custom dashboard;
the account only needs Django's `Staff status` if it must also enter raw Django
admin. The navigation link appears only for a Staff account that is a superuser
or has at least one raw model permission. Running `setup_roles` again replaces
the three groups' permissions with the documented least-privilege sets, but
never creates, edits, or assigns users.

The Django account is only for managing this website. It is not a Jackrabbit
owner/manager, instructor Staff Portal, or customer Parent Portal account, and
credentials should never be reused between those systems. Superusers have every
Django permission automatically. Failed login attempts are rate-limited and
locked for one hour after five failures for the same username and IP-address
combination.

For normal editing, follow the [administrator guide](docs/ADMIN_GUIDE.md). Use
raw Django admin primarily for user accounts, groups, and password changes.

## Website content management

Managers use `/dashboard/content/` instead of raw Django admin for normal work:

- **Website details & homepage** controls contact information, external links,
  SEO text, section copy and visibility, logo, favicon, hero, and section images.
- **Programs**, **Events**, **Homepage highlights**, and **Social links** support
  publishing controls and numeric display order. Programs can be featured as
  homepage cards or shown in the specialty list. Events can include public
  schedule and price notes.
- Image controls show the currently saved picture and let managers upload,
  preview, replace, or remove JPEG, PNG, and WebP files. Program and Event lists
  also show picture thumbnails and fallback status.
- **Jackrabbit links and public guidance** control where new families register,
  existing families manage their accounts, visitors see the live class
  schedule, and authorized staff open Jackrabbit's owner or Staff Portal tools.

Use plain text rather than HTML. Provide accurate alternative text for each
meaningful image. Uploads are limited to validated JPEG, PNG, or WebP images up
to 8 MB, 6,000 pixels per dimension, and 24 megapixels. Bundled images remain as
fallbacks until a manager uploads approved replacements. Homepage and business
settings become live immediately when saved. Collection records also require
**Published**; events additionally obey their publish/expiration window. Use
**Save and view website** to review a change immediately.

Uploaded files are development data and are ignored by Git. In production they
live in the persistent Docker volume `media_data`, not in the replaceable app
container.

## Jackrabbit enrollment and payment workflow

Jackrabbit is the source of truth for class availability, tuition, family and
student records, policies, enrollment, balances, payments, refunds, and business
reporting. The Django website provides clear links into those hosted workflows:

1. New families use **Online Registration** to create their family record,
   select an available class or trial, accept policies, and provide the billing
   details required by Gyminators.
2. Existing families use the **Parent Portal** to view their account, enroll in
   available programs, manage billing information, and make payments.
3. The public **Live class schedule** opens Jackrabbit's hosted listings. The
   private reporting dashboard also caches Jackrabbit's public JSON class feed
   for searchable schedule, openings, and published-tuition reporting.
4. Owners and managers use the separate **Jackrabbit owner/manager login** for
   transactions, customer records, dashboards, and reports. Instructors use the
   separate **Jackrabbit Staff Portal** for schedules, attendance, and skills.

Managers can update all five destination URLs under **Dashboard > Content >
Homepage and business details > Jackrabbit links**. Confirm the organization ID
and test every destination after changing one. Do not place Jackrabbit
passwords, payment credentials, the Jackrabbit Zapier API key, or card details
in Django fields or environment variables. The `JACKRABBIT_WEBHOOK_TOKEN`
described below is a separate secret generated by Gyminators for inbound Zapier
requests.

Fresh installations show the enrollment section and registration calls to
action by default for organization `154877`. Do not expose a fresh installation
to the public until the owner has verified the Online Registration, Parent
Portal, live schedule, fee posting, policy, and ePayment behavior end to end.

Jackrabbit setup references:

- [Online Registration](https://help.jackrabbitclass.com/help/online-registration-form-overview)
- [Parent Portal](https://help.jackrabbitclass.com/help/jackrabbit-parent-portal-overview)
- [Process ePayments](https://help.jackrabbitclass.com/help/epayments-process-credit-cards-bank-drafts)
- [Online class listings](https://help.jackrabbitclass.com/help/online-class-listings)
- [Executive Dashboard](https://help.jackrabbitclass.com/help/executive-dashboard-overview)

The owner must configure payments inside Jackrabbit before publishing the calls
to action. Complete the Jackrabbit ePayment Wizard and confirm the payment
partner or Jackrabbit Pay account, accepted payment methods, settlement schedule,
Online Registration and Parent Portal payment settings, tuition and registration
fee posting, billing cycles, payment schedules, automated payments, receipts,
staff permissions, policies, refunds/voids, failed payments, and reconciliation.
Test both a new-family registration and an existing-family Parent Portal payment
using the procedure approved by Jackrabbit and the configured payment partner.

The website never receives card data, balances, subscriptions, or transaction
records. The reporting ledger stores only approved opaque family/contact/student/
class/enrollment identifiers, event type, event time, source, and optional
location. It rejects extra fields so names, email, phone, addresses, dates of
birth, notes, and billing data are not accidentally copied. Retired website
payment URLs redirect families to the Parent Portal, and the retired Stripe
webhook endpoint returns HTTP 410.

## Reporting scope

Authorized Reporting Managers can use `/dashboard/reporting/` for:

- new family, contact, student, and lead activity;
- enrollments, drops, and net enrollment activity;
- waitlist additions, removals, and net activity;
- inactive-student and distinct churn signals;
- trends over 7, 30, 90, or 365 days; and
- the cached public class schedule, openings, waitlist state, and published
  tuition.

Operational metrics arrive through nine deliberately small Zapier mappings.
The endpoint is versioned, bearer-token authenticated, size limited,
idempotent, and rejects fields outside the approved schema. A metric remains
**Awaiting this Zap/backfill** until its first event arrives. Every dashboard
shows its earliest stored event, first/latest delivery, conservative coverage
date, and freshness. Previous-period comparisons remain unavailable until the
stored feed is old enough to support them; the data is not represented as an
all-time or complete Jackrabbit replica. Follow the
[Zapier activation guide](docs/JACKRABBIT_ZAPIER_SETUP.md).

There is still no payment API or financial webhook synchronization. Published
tuition is a listing price, not revenue. For per-day classes, the displayed
range represents total tuition based on days selected—not a per-day rate.
Payment status, balances, charges,
refunds, subscriptions, deposits, accounts receivable, and income remain in
Jackrabbit's Executive Dashboard and financial reports.

The public class feed can be refreshed once with:

```powershell
& .\.venv\Scripts\python.exe manage.py sync_jackrabbit_classes
```

Use `manage.py check_jackrabbit_reporting` to inspect event coverage and the
latest class synchronization without showing source identifiers.

## Production deployment

The production stack contains Caddy for automatic HTTPS, Django/Gunicorn,
PostgreSQL with a persistent volume, a 15-minute class-feed synchronization
service, a persistent uploaded-media volume, and a backup service for both data
stores.

```bash
cp .env.example .env
chmod 600 .env
# Generate JACKRABBIT_WEBHOOK_TOKEN separately and paste it into .env:
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
nano .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs -f app caddy
```

Point the domain to the VPS and allow TCP ports 22, 80, and 443 plus UDP 443.
Do not expose PostgreSQL port 5432. Confirm:

```text
https://YOUR_DOMAIN/api/health
```

Create the first owner account:

```bash
docker compose exec app python manage.py createsuperuser
docker compose exec app python manage.py setup_roles
docker compose exec app python manage.py sync_jackrabbit_classes
docker compose exec app python manage.py check_jackrabbit_reporting
```

This creates an account in production PostgreSQL. Local SQLite administrator
credentials do not work in production unless a separate production account is
created. Never copy a temporary password into Git or documentation.

Deploy updates with:

```bash
git pull --ff-only
docker compose up -d --build
```

Django migrations run before Gunicorn starts. Use a dedicated migration/release
step before running more than one app replica. Never run
`docker compose down -v` in production because `-v` deletes persistent volumes.

### Upgrading a retired Stripe installation

Fresh installations need no special step. Migration `0005_jackrabbit_only`
deliberately stops if an older deployment still contains local Stripe plans,
customers, subscriptions, payments, payment requests, or webhook records.
Before upgrading such an installation, stop the old payment workflow, export
and retain the required accounting history, reconcile and migrate or cancel any
live billing without double-charging families, and have a developer approve the
legacy-record cleanup. Do not bypass the migration guard or assume a normal
`docker compose up` completes that business transition.

## Backups

The commands below back up the production PostgreSQL and media volumes. For a
stopped local SQLite/media snapshot, follow the
[administrator guide](docs/ADMIN_GUIDE.md#backups-and-restores).

```bash
mkdir -p backups
docker compose --profile backup run --rm backup
```

Each run creates a matched pair with one timestamp:

```text
backups/gyminators-TIMESTAMP.dump
backups/gyminators-media-TIMESTAMP.tar.gz
```

The first file is a PostgreSQL custom-format dump; the second contains all
manager-uploaded pictures. The database dump also contains the minimal
Jackrabbit-derived event ledger and cached public classes, so it must be treated
as business-sensitive. Local database and media backups older than 30 days
are removed. Always copy both matching files to encrypted off-site storage and
test complete restores regularly. A database dump alone is not a complete
backup of this application.

Example nightly cron:

```cron
15 3 * * * cd /opt/gyminators && /usr/bin/docker compose --profile backup run --rm backup >> /var/log/gyminators-backup.log 2>&1
```

Full restore outline:

```bash
docker compose --profile backup run --rm backup
docker compose stop app class-sync
docker compose --profile backup run --rm --entrypoint /bin/sh backup \
  /usr/local/bin/restore /backups/gyminators-TIMESTAMP.dump
docker compose start app class-sync
docker compose logs --tail=100 app
```

The restore command infers the matching media archive from the database dump's
timestamp. A second archive path may be passed explicitly. It validates and
stages media before replacement, but the database restore and media replacement
are not one atomic transaction; a later failure can leave a partial restore.
Keep the app stopped, take a fresh complete backup first, use a tested matching
pair, schedule a maintenance window, and verify both the site and logs before
reopening access. A restore loses Zapier deliveries received after the selected
backup. Run a class resync immediately, then use the documented Zapier searches
to reconcile the missing operational period before relying on dashboard totals.

## Verification

```powershell
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py makemigrations --check
& .\.venv\Scripts\python.exe manage.py test
& .\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Run the production security check from PowerShell with temporary values:

```powershell
$env:DJANGO_DEBUG="false"
$env:DJANGO_SECRET_KEY="temporary-long-check-key-that-is-not-used-in-production"
$env:DOMAIN="example.com"
$env:ALLOWED_HOSTS="example.com"
$env:CSRF_TRUSTED_ORIGINS="https://example.com"
$env:JACKRABBIT_WEBHOOK_TOKEN = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
& .\.venv\Scripts\python.exe manage.py check --deploy
Remove-Item Env:DJANGO_DEBUG,Env:DJANGO_SECRET_KEY,Env:DOMAIN,Env:ALLOWED_HOSTS,Env:CSRF_TRUSTED_ORIGINS,Env:JACKRABBIT_WEBHOOK_TOKEN -ErrorAction SilentlyContinue
```

Before launch, complete [the owner approval checklist](docs/OWNER_CHECKLIST.md).
The live-site comparison is recorded in [the content audit](docs/CONTENT_AUDIT.md).
