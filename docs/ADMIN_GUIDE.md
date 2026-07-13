# Gyminators website administrator guide

This guide is for owners and managers who maintain the public Gyminators
website. It uses plain-language steps and reflects the current website manager.
It does not contain a username or password. Keep credentials in an approved
password manager and never place them in website content fields.

Last reviewed: July 13, 2026.

## Quick navigation

- [Everyday editing workflow](#everyday-editing-workflow)
- [Sign in, sign out, and change a password](#sign-in-sign-out-and-change-a-password)
- [Edit homepage and business details](#edit-homepage-and-business-details)
- [Manage the Jackrabbit links](#manage-the-jackrabbit-links)
- [Manage programs](#manage-programs)
- [Manage events](#manage-events)
- [Manage homepage highlights](#manage-homepage-highlights)
- [Manage social links](#manage-social-links)
- [Pictures and alternative text](#pictures-and-alternative-text)
- [Use the business activity dashboard](#use-the-business-activity-dashboard)
- [Add staff and assign website roles](#add-staff-and-assign-website-roles)
- [Backups and restores](#backups-and-restores)
- [Troubleshooting](#troubleshooting)
- [Safe publishing checklist](#safe-publishing-checklist)

## Everyday editing workflow

1. Sign in at `/staff/login/` using the website account—not a Jackrabbit
   account.
2. Select **Manage content**.
3. Open the content area you need and make the approved change.
4. Check publishing, visibility, dates, display order, links, and image
   alternative text.
5. Select **Save and view website** when available.
6. Review the public page on both a computer and a phone-sized screen, then
   test every changed link while signed out.
7. Return to the dashboard and **Log out** when finished.

Use the website's **Business activity reports** for the limited operational
signals described below. Use Jackrabbit itself for individual family or student
records, enrollment decisions, authoritative class status, billing, payments,
refunds, revenue, and financial reports.

## Two separate systems

The website and Jackrabbit have different jobs and different accounts.

| System | Use it for | Do not use it for |
| --- | --- | --- |
| Gyminators website manager | Public content and pictures; limited aggregate activity reports; a read-only cached copy of published classes, openings, and listing tuition | Editing authoritative Jackrabbit records; billing, card details, payments, refunds, revenue, or financial reports |
| Jackrabbit | Families and students, classes, openings, enrollment, tuition and fees, policies, billing, payments, refunds, staff operations, and business reporting | Editing the design or wording of the Gyminators public website |

A website login does not grant access to Jackrabbit. A Jackrabbit login does not
grant access to the website manager. Use separate passwords for the two systems.

## Start the website on a local computer

The production website is normally already running; an owner editing the hosted
site does not run these commands. Use these steps only to inspect the local copy
on a Windows development computer.

1. Open PowerShell in `C:\Projects\Gyminators_Web`.
2. If the project has already been set up, run:

   ```powershell
   & .\.venv\Scripts\python.exe .\run.py
   ```

3. Wait for the browser to open at `http://127.0.0.1:8000/`.
4. Leave PowerShell open while reviewing the site. Press `Ctrl+C` in that window
   to stop it.

For a new development setup, run these commands once:

```powershell
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe .\run.py --create-admin
```

The last command asks interactively for a new website administrator. The
password is hidden while it is typed. Do not create a new administrator every
time the site starts. On later runs, use `run.py` without `--create-admin`.

The launcher prepares the local database and website-manager roles before it
starts. If port 8000 is already in use, run `run.py --port 8001` and use the URL
shown in PowerShell.

Do not use `--host 0.0.0.0` unless a developer intentionally needs a short test
on a trusted local network. It exposes Django's DEBUG development server and is
never appropriate for an internet-facing or production site.

> Local and production data are separate. A change made at
> `127.0.0.1:8000` does not update the hosted website.

## Sign in, sign out, and change a password

### Sign in

1. Open `/staff/login/` on the correct site. Locally, this is
   `http://127.0.0.1:8000/staff/login/`. In production, use
   `https://YOUR-DOMAIN/staff/login/`.
2. Enter the website username and password, not Jackrabbit credentials.
3. Select **Open website dashboard**.

Five failed attempts from the same username and network address cause a
one-hour lockout. If a login is rejected, check the spelling and Caps Lock
before trying again. Do not keep guessing.

### Sign out

Use **Log out** in the dashboard or content-manager navigation. On a shared
computer, close the browser after signing out.

### Change a password

An active staff administrator can open **Django admin** from the dashboard,
select **Change password** in the upper-right corner, and enter the current and
new passwords. The direct address is `/django-admin/password_change/`.

A dashboard-only Website Manager does not have access to raw Django admin and
therefore cannot use that password-change screen. A site administrator must
reset that person's password under **Django admin > Users**, then deliver it
through a secure channel. There is currently no email-based password reset.

For a command-line reset, a technical administrator can run:

```powershell
& .\.venv\Scripts\python.exe .\manage.py changepassword USERNAME
```

In production, use `docker compose exec app python manage.py changepassword
USERNAME` instead. Never send a password in email, chat, documentation, or a
support ticket.

## Find your way around the dashboard

After sign-in, the dashboard provides these destinations:

- **Manage content** opens all public website editing areas.
- **Homepage details** is a shortcut to the main site and homepage form.
- **Business activity reports** opens approved non-financial activity metrics
  and the cached public class schedule. It appears only for an account with the
  reporting permission.
- **View website** opens the public homepage.
- **Django admin** appears only for a Staff account that is a superuser or has
  at least one raw model permission. Normal content work should be done in
  **Manage content**.
- The Jackrabbit cards open the owner/manager login, instructor Staff Portal,
  Online Registration, Parent Portal, and live class schedule in Jackrabbit.
- **Log out** ends the website session.

The content manager contains **Homepage and business details**, **Programs**,
**Events**, **Homepage highlights**, and **Social links**. A user sees only the
areas their website role permits.

## Save changes safely

The website does not have a separate preview copy. Homepage and business-detail
changes are immediately live when saved. Programs, events, highlights, and
social links also require **Published**; events additionally follow their
publication and expiration window.

- **Save changes** on the homepage form saves and keeps you on that form.
- **Save program/event/highlight/social link** saves and returns to that
  collection's list.
- **Save and view website** saves and opens the public homepage so you can check
  the result immediately.
- **Cancel** leaves without saving. The browser warns before leaving a form that
  has unsaved changes.

If a field is invalid, the form stays open and shows the problem near that
field. Nothing is saved until all errors are corrected. Use plain text; do not
paste HTML, scripts, passwords, payment details, or private customer data.

## Edit homepage and business details

Go to **Dashboard > Manage content > Homepage and business details**. The form
is divided into sections:

- **Business details** controls the gym name, announcement, phone, email,
  address, hours note, opening year, and public age range.
- **Jackrabbit links** controls the five website destinations described in the
  next section.
- **Other links** contains the map and accessibility links.
- **Search and branding** contains the browser/search title and description,
  logo, favicon, and logo alternative text.
- **Hero** controls the large first image, headline, supporting copy, and button
  labels.
- **Introduction** controls the opening text beneath the hero.
- **Jackrabbit registration and payments** controls the public explanation and
  button wording for new and existing families. It does not configure payments.
- **Programs**, **Why Gyminators**, and **Events** control each section's heading,
  introductory copy, images where offered, and show/hide setting.
- **Trial and footer** controls the trial callout, footer text, credentials, and
  optional privacy, terms, and cancellation/refund destinations. The
  accessibility destination is under **Other links**.

The **Show ...** checkboxes control whole homepage sections. Turning one off
hides that section without deleting its content. Programs, Enroll & Pay, Why
Gyminators, and Events also have matching navigation links that disappear; the
Trial section has no navigation link. Hiding is the safest way to temporarily
remove a section.

Review contact details and factual claims with the owner before saving. Add only
approved policy links; leaving an optional policy URL blank hides that footer
link.

## Manage the Jackrabbit links

Go to **Homepage and business details > Jackrabbit links**. These fields are
website links, not Jackrabbit settings:

- **Registration URL** sends new families to Jackrabbit Online Registration and
  is used by the header, hero, trial, and fallback program registration buttons.
- **Portal URL** sends existing families to the Jackrabbit Parent Portal.
- **Class schedule URL** opens Jackrabbit's public class listings, prices, and
  openings.
- **Jackrabbit owner URL** is shown to signed-in website managers for business
  operations and reporting.
- **Staff portal URL** is shown to signed-in managers for instructor tools.

Only use owner-approved URLs for the correct Gyminators organization. After a
change, select **Save and view website**, then test all five destinations in a
private/incognito browser window. Confirm that registration, Parent Portal, and
the class schedule belong to Gyminators before leaving the change live.

Never paste a Jackrabbit username, password, API key, merchant credential, or
card information into a URL or content field.

The live class-schedule card's heading, explanatory sentence, and button label,
along with several navigation and footer labels, are part of the website design
and are not editable fields. Its destination URL is editable. Ask a developer
if those fixed interface labels need to change.

## Manage programs

Go to **Manage content > Programs**. Select **Add program** for a new one or
**Edit** beside an existing one.

- **Name**, **age range**, and **description** are public content.
- **Slug** is an internal unique name. Leave it blank for a new program and the
  website creates it from the program name. Normally, do not change an existing
  slug.
- **Image** and **image alt** control the program picture and its accessible
  description.
- **Call to action URL** can point to the matching approved Jackrabbit page. If
  it is blank, the button uses the main Online Registration URL.
- **Call to action label** describes the action, such as “Register.”
- **Featured** displays the program as a full homepage card. A published program
  that is not featured appears by name in the smaller “Also available” list.
- **Published** determines whether the program is public.
- **Display order** controls placement; lower numbers appear first.

Use **Published** to remove a program temporarily. Delete is permanent and
should be reserved for records that were created by mistake.

Keep actual class schedules, capacity, openings, waitlists, tuition, and fees in
Jackrabbit. A website program is marketing content, not a class record.

## Manage events

Go to **Manage content > Events**. An event can include:

- A title, description, image, and alternative text.
- An approved external URL and public button label. With no URL, the event sends
  visitors to the website contact section.
- A short schedule note and an optional owner-approved public price note.
- A start date that can appear publicly when no schedule note is supplied. The
  end date is currently administrative and is not displayed on the homepage.
- A **Publish at** date for delayed publication and an **Expires at** date for
  automatic removal.
- A **Published** checkbox and numeric **Display order**.

Start and end dates do not automatically control visibility. An event appears
only when **Published** is checked, its **Publish at** time has arrived (or is
blank), and its **Expires at** time has not passed (or is blank). The expiration
must be after publication, and the end must be after the start.

Lower display-order numbers appear first. If a precise schedule note is present,
it is shown instead of the start date. Confirm dates, eligibility, and prices
with the owner. Prefer a Jackrabbit destination for registration, and keep the
authoritative enrollment status and charges in Jackrabbit.

## Manage homepage highlights

Go to **Manage content > Homepage highlights**. Each short title-and-body item
belongs to one of two locations:

- **Hero proof point** appears over the bottom of the hero area.
- **Why Gyminators benefit** appears in the “Why Gyminators” section.

Check **Published** to show an item. Use **Display order** to arrange items,
with lower numbers first. Keep these statements brief and factual so they remain
readable on phones.

## Manage social links

Go to **Manage content > Social links**. Enter the public label and the full
approved profile URL. Published links appear in the footer, ordered from the
lowest display-order number to the highest. Test each link while signed out of
the social network so it does not lead to a personal or private page.

## Pictures and alternative text

Pictures are edited alongside the content they belong to:

- From the dashboard, select **Homepage & pictures** to change the logo,
  favicon, hero photograph, or **Why Gyminators** photograph.
- Open **Manage content > Programs** to change a program-card photograph.
- Open **Manage content > Events** to add or change an event thumbnail.

To upload or replace a picture:

1. Open the page or item you want to edit. If it already has an uploaded
   picture, the form shows a **Current picture** thumbnail and an **Open full
   size** link.
2. Select **Choose a picture** or **Choose a replacement**, then select the
   approved file from the computer or device.
3. Review the **New picture preview**, filename, pixel dimensions, and file
   size shown by the form.
4. Review and update the nearby alternative-text field so it describes the
   new picture rather than the old one.
5. Select **Save and view website** and inspect the public page on both a wide
   screen and a phone-sized screen.

To remove an uploaded picture, select **Remove current picture when I save**
and save the form. The current thumbnail dims before saving. Removing an upload
may reveal a bundled fallback where one is configured; otherwise that content
will have no picture. Replaced and removed uploads are deleted from website
storage after the content change succeeds.

The website accepts JPEG, PNG, and WebP files with these limits:

- Maximum file size: 8 MB.
- Maximum width or height: 6,000 pixels.
- Maximum total image size: 24 megapixels.

SVG, GIF, HEIC, PDF, and other file types are not accepted. For faster pages,
resize and compress photographs before uploading. Use a wide landscape image
for the hero and content cards, a clear logo file (often PNG), and a small
square image for the favicon. The dashboard does not crop or rotate files, and
the public layout may trim the edges of a photograph to fit its space.

Alternative text tells a person using a screen reader what a meaningful image
shows. Describe the subject and useful context in one short sentence, for
example, “Coach helping a young gymnast balance on the beam.” Do not write
“image of,” repeat nearby text, add search-keyword lists, or identify a child by
name without approval. Program images require alternative text, and an uploaded
event image cannot be saved without it.

The Programs and Events list pages show a small thumbnail and identify whether
the item uses an uploaded picture, a bundled fallback, or no picture.

## Use the business activity dashboard

Open **Dashboard > Business activity reports**. This area is available only to
superusers and members of **Reporting Managers**. It is a limited operational
view, not a replacement for Jackrabbit's customer, enrollment, or financial
reports.

Choose the last 7, 30, 90, or 365 days and select **Apply**. Each available card
shows the selected period. It shows the immediately preceding period of the same
length only after that feed has enough stored coverage; otherwise the comparison
is marked unavailable:

- **New families, contacts, students, and leads** count creation events received
  through the corresponding Zapier connection. Those are different Jackrabbit
  record types and should not be added together as a customer total.
- **Enrollments** and **drops** count class activity. **Net enrollment activity**
  is enrollments minus drops during the period; it is not the current number of
  enrolled students.
- **Waitlist additions**, **waitlist removals**, and their net activity measure
  movement during the period. They are not the current waitlist size.
- **Students inactive** and **students with churn signals** identify received
  inactive or drop activity. A signal is not proof that a family has left the
  business and should be checked in Jackrabbit before follow-up.

A card marked **Awaiting this Zap/backfill** has not received that event type.
It deliberately does not show zero. The coverage panel records when each feed
first delivered data, and each card identifies the date from which coverage is
evidenced. The page also shows the latest delivery time. Unless an
approved historical backfill was completed, totals only cover activity after
the connection began. Follow the
[Jackrabbit Zapier setup guide](JACKRABBIT_ZAPIER_SETUP.md) when activating,
testing, repairing, or backfilling a feed.

A trend value labeled **unverified coverage** is a stored historical event that
arrived after the date shown. The event is included, but that late delivery does
not prove every event in the intervening dates was backfilled. The first and
last chart buckets can also be labeled partial because the selected rolling
window begins or ends partway through a day, week, or month.

The class area is a read-only cache of Jackrabbit's public class feed. Select
**Browse class schedule** to search and filter by category, session, location,
day, or availability. Openings are not total capacity, and published tuition is
a listing price—not collected income. Per-day classes show the total-tuition
range for the available number of selected days, not a per-day rate. The row's
**Open registration page** link is the public registration or waitlist page;
open the Jackrabbit owner portal before making an enrollment or financial
decision.

Production refreshes the class cache about every 15 minutes. The dashboard
shows the last successful refresh and warns if the data is stale or the latest
attempt failed; a failed refresh keeps the last good copy. A class omitted once
also remains visible until a second valid feed confirms its removal, and the
dashboard warns during that confirmation window. Only a superuser or
an account explicitly granted the class-sync permission sees **Refresh now**.
Normal Reporting Managers should not need that control.

This website stores only approved event types, timestamps, optional location,
and opaque Jackrabbit identifiers for these reports. It does not provide a
customer-name lookup and must never receive names, contact details, birthdates,
notes, balances, payment data, or raw Zapier payloads.

## Add staff and assign website roles

Only a trusted site administrator should manage user accounts. The application
has three groups:

- **Website Managers** can edit public website content and pictures. Use this
  group for new content editors.
- **Business Managers** is retained for existing assignments and currently has
  the same content permissions as Website Managers. Do not use it for new
  accounts, and do not assume it grants reporting access.
- **Reporting Managers** can view the limited business activity dashboard and
  cached public class data. It cannot edit content or browse raw imported events
  and classes, and it does not grant access to Jackrabbit itself.

An owner who needs both content editing and reports should belong to **Website
Managers** and **Reporting Managers**. Otherwise assign only the group needed.

1. Sign in with a superuser or authorized staff administrator.
2. Open **Django admin**, then **Users**.
3. Select **Add user**, enter a unique username and a strong initial password,
   and save.
4. Open the new user again. Add the person's name and work email.
5. Leave **Active** selected and add **Website Managers**, **Reporting
   Managers**, or both according to the approved job duties. Retain **Business
   Managers** only for an existing legacy assignment.
6. Leave **Superuser status** off for normal owners and managers.
7. **Staff status** is not needed for the friendly content manager. Enable it
   only if the person must enter raw Django admin.
8. Save and provide the site address and credentials through a secure channel.
   A dashboard-only manager has no self-service password-change screen, so an
   administrator must assist with future rotations. If Staff status was granted,
   require the user to change the initial password in Django admin immediately.

Do not assign individual permissions unless a developer has reviewed the need.
To remove access, clear **Active** or remove the group and save. Do not delete an
account merely because someone leaves; retaining it preserves the name attached
to past edits.

After a new installation or permission update, a technical administrator runs:

```powershell
& .\.venv\Scripts\python.exe .\manage.py setup_roles
```

In production, run `docker compose exec app python manage.py setup_roles`. This
creates or refreshes all three groups but never creates users or assigns a
person to a group.

## What the owner must manage in Jackrabbit

Use an authorized Jackrabbit owner/manager account to maintain:

- Families, students, emergency details, enrollments, and staff access.
- Classes, sessions, times, capacity, openings, waitlists, and registration
  availability.
- Tuition, registration fees, discounts, proration, taxes, due dates, billing
  schedules, and policy agreements.
- The ePayment Wizard, Jackrabbit Pay or the approved gateway, accepted payment
  methods, saved-payment rules, settlements, receipts, and staff permissions.
- Charges, payments, declines, refunds, voids, account credits, disputes, and
  reconciliation.
- Customer, revenue, deposit, and payment reports.

Before launch, test the complete Online Registration path for a new family and
the Parent Portal path for an existing family. Confirm charges, policies,
receipts, deposits, cancellations, refunds, and reports using a procedure
approved by Jackrabbit and the payment provider; test transactions may create
real charges.

Changing wording or links on the website does not configure any of the above.
The website stores no card data, customer profiles, balances, transactions, or
financial totals. Its reporting copy is limited to approved opaque identifiers,
event types and timestamps, optional location, and cached fields from the public
class feed. Jackrabbit remains the authoritative record.

## Backups and restores

Production website backups contain a matched pair:

```text
backups/gyminators-TIMESTAMP.dump
backups/gyminators-media-TIMESTAMP.tar.gz
```

The `.dump` contains the website's PostgreSQL database, including content,
website user accounts, the limited operational event ledger, and cached public
classes. The `.tar.gz` contains manager-uploaded pictures. Both files with the
same timestamp are required for a complete website backup. Treat the database
copy as business-sensitive even though it does not contain customer names or
financial records.

A technical administrator creates a production backup with:

```bash
docker compose --profile backup run --rm backup
```

Copy both files to encrypted off-site storage. The server-side backup task
removes its local backup files after 30 days, so the server must not be the only
copy.

These backups do **not** include complete or authoritative Jackrabbit records,
payment-provider records, the source-code repository, DNS, website secrets in
`.env`, email accounts, or other third-party services. Jackrabbit data
protection and exports are separate and must follow Jackrabbit's procedures.

The production restore is a full replacement, not an undo button for one page.
It rolls website content, uploaded pictures, website accounts, reporting events,
and the class cache back to the selected timestamp. A technical administrator
must take a fresh backup, verify the matching pair, schedule downtime, stop both
the web app and class-sync worker, perform the restore, restart both services,
and check the logs and public site.
Run a class refresh and reconcile any Zapier events delivered after the restored
timestamp before relying on the dashboard. Never restore while someone is
editing, and never run `docker compose down -v` because it deletes persistent
volumes.

The local development copy uses `data/gyminators-django.db` and the `media/`
folder. The production Docker backup command does not back up those local files.
See the [technical README](../README.md) for the tested restore command and
deployment details.

For a local snapshot, stop `run.py` with `Ctrl+C`, then copy both the SQLite
database and media directory:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$destination = ".\backups\local-$stamp"
New-Item -ItemType Directory -Path $destination -Force
Copy-Item ".\data\gyminators-django.db" $destination
if (Test-Path ".\media") { Copy-Item ".\media" $destination -Recurse }
```

Treat this directory as sensitive because it contains website users, content,
and potentially limited reporting events and class data. Keep the server stopped
when replacing those files during a local restore, and have a technical
administrator verify the selected snapshot first.

## Troubleshooting

### The local site will not start

- Confirm PowerShell is in `C:\Projects\Gyminators_Web`.
- Use `.venv\Scripts\python.exe`, not a deleted `.audit-venv` interpreter.
- If Django is missing, run the requirements installation command in the
  startup section.
- If port 8000 is busy, use `run.py --port 8001`.

### The login is rejected or locked

- Confirm this is the website username, not a Jackrabbit email or Parent Portal
  login.
- Check Caps Lock and the exact username before retrying.
- Stop after a few failures. Five failures cause a one-hour lockout.
- Ask a site administrator to confirm the account is Active and reset its
  password securely if necessary.

After verifying the person's identity, a technical administrator can clear a
username lockout locally with:

```powershell
& .\.venv\Scripts\python.exe .\manage.py axes_reset_username USERNAME
```

In production, use `docker compose exec app python manage.py
axes_reset_username USERNAME`. Resetting a lockout does not change the password.

### The dashboard says access is denied

Ask a site administrator to confirm that the account is Active and belongs to
Website Managers for content access, Reporting Managers for report access, or
both when approved. Business Managers only supplies its legacy content access.
A technical administrator should also run `setup_roles` after a new installation
or permission update.

### A reporting card says Awaiting this Zap/backfill

That event type has never been received. Do not interpret it as zero. Ask the
technical administrator to check the matching Zap, token configuration, and
delivery history using the [Zapier setup guide](JACKRABBIT_ZAPIER_SETUP.md).

### The class feed is stale or needs attention

Continue using Jackrabbit itself for current decisions. A technical
administrator can run `python manage.py check_jackrabbit_reporting` to inspect
status without revealing source identifiers, then run
`python manage.py sync_jackrabbit_classes`. A failed refresh leaves the last
successful class copy in place.

### The Django admin link is missing

This is expected for a dashboard-only manager. The link appears only when the
account has Staff status and either superuser access or at least one raw model
permission. Group membership independently controls the friendly content
manager and reporting dashboard.

### A saved item does not appear

- Confirm the save succeeded and no validation error remains.
- Confirm the item is Published and the entire homepage section is shown.
- For an event, check Publish at and Expires at.
- Check whether its display-order number places it farther down the page.
- Refresh the public page. Confirm you are viewing local or production as
  intended.

### A picture will not upload

Confirm it is a valid JPEG, PNG, or WebP, no larger than 8 MB, within the pixel
limits, and supplied with required alternative text. Export uncommon phone or
design formats to JPEG, PNG, or WebP first.

### A Jackrabbit button goes to the wrong place

Return to **Homepage and business details > Jackrabbit links**, compare the URL
with the owner-approved Gyminators destination, correct it, save, and retest in
a private browser. Changing this website link does not repair settings inside
Jackrabbit.

## Safe publishing checklist

Before editing:

- Confirm whether you are on the local copy or the production site.
- Confirm the wording, dates, prices, policy links, and images with the owner.
- Keep class pricing, availability, enrollments, and payments authoritative in
  Jackrabbit. The reporting dashboard's public-feed cache is read-only and may
  be delayed.
- Take a complete matched production backup before bulk or high-impact work.

Before saving:

- Remove private information, credentials, card data, and unapproved claims.
- Check spelling, phone, email, dates, age ranges, and all destination URLs.
- Add useful alternative text to every meaningful uploaded picture.
- Check Published, Featured, section visibility, publication dates, expiration,
  and display order.

After saving:

- Use **Save and view website** and inspect the changed area on both a wide
  screen and a phone-sized screen.
- Test public links while signed out, especially Registration, Parent Portal,
  class schedule, policies, maps, and social profiles.
- Test Jackrabbit changes in Jackrabbit itself; the website cannot confirm
  enrollment or payment behavior.
- If something should be removed temporarily, unpublish it or hide its section
  instead of deleting it.
- Log out when finished, especially on a shared computer.

Business decisions still awaiting owner approval are tracked in the
[owner checklist](OWNER_CHECKLIST.md).
