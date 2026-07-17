# Owner approval checklist

Most items require business or legal decisions and cannot be safely inferred
from the current website. The approved waiver-text baseline below records the
client's explicit legal-team confirmation; the remaining launch gates still
require completion.

Use this with the [administrator guide](ADMIN_GUIDE.md). Do not record passwords,
payment credentials, bank details, or Jackrabbit API keys in this checklist.

- Confirm whether the published `$60` annual registration and `$85 / $125 /
  $155` monthly tuition amounts remain current, then maintain the approved fees
  in Jackrabbit. Django does not maintain a second editable price catalog; its
  public `/class-schedule/` page and private reporting page read tuition from the
  same cached Jackrabbit public feed.
- Confirm organization ID `154877`. Test Online Registration, Parent Portal,
  and `/class-schedule/` from the public site. Confirm the calendar shows only
  classes with published start years in the current or next calendar year and
  that each class action opens the correct class-specific Jackrabbit
  registration or waitlist page. Confirm the general Jackrabbit class listing
  is not used as a customer-facing destination. Test all five configured
  Jackrabbit reference and workflow URLs, including owner/manager and instructor
  Staff Portal, from the signed-in Django dashboard.
- Approve the nine non-financial Zapier connections described in the
  [Jackrabbit Zapier setup guide](JACKRABBIT_ZAPIER_SETUP.md): family, contact,
  student, and lead creation; enrollment and drop; waitlist addition and
  removal; and student inactive. Confirm the available Jackrabbit/Zapier plan,
  polling frequency, and named staff owner for monitoring failed tasks.
- Approve the minimum-data rule for those connections. Send only event type,
  event time, source, optional location, and opaque Jackrabbit identifiers.
  Disable `IncludeAllContacts` and never send names, email, phone, address,
  birthdate, notes, balances, transactions, or a raw trigger payload.
- Generate a unique `JACKRABBIT_WEBHOOK_TOKEN` for the website, store it only in
  the approved infrastructure secret store, and test token rotation. This is an
  inbound Gyminators secret—not a Jackrabbit API key—and must not be pasted into
  this checklist or a website content field.
- Activate and test each connection separately. Decide which supported searches
  will be used for an approved historical backfill, record the real tracking
  start for feeds that cannot be fully backfilled, and accept that pre-activation
  activity may be absent. Review the dashboard's coverage and freshness panel
  before using a metric operationally.
- Approve a retention period and access policy for the opaque reporting ledger.
  Document how failed Zapier tasks, token exposure, downtime, and a database
  restore will be detected and reconciled before dashboard totals are trusted.
- Complete Jackrabbit's ePayment Wizard and confirm that Jackrabbit Pay or the
  selected supported gateway and merchant account is approved for live use.
- Configure accepted cards and/or bank drafts, gateway settlement timing,
  receipt notifications, staff ePayment permissions, and access for users who
  may process payments, voids, or refunds.
- Configure new-family Online Registration: displayed classes, enrollment and
  waitlist rules, policy agreements, required billing information, when tuition
  and registration fees post, and whether payment is required at checkout.
- Configure the existing-family Parent Portal: enrollment permissions, whether
  families may make payments, whether enrollment requires payment, available
  one-time or saved payment methods, policy renewals, and account messaging.
- Confirm the annual registration-fee rules in Jackrabbit for new and returning
  families, including timing, family/student scope, maximums, and exceptions.
- Confirm tuition billing cycles, posting dates, due dates, proration, discounts,
  taxes, late fees, ePayment schedules, and automated-payment tasks in Jackrabbit.
- Document cancellations, refunds, voids, declined cards, returned bank drafts,
  account credits, charge disputes, and bank-reconciliation procedures.
- Run an owner-approved end-to-end test for new-family registration, an existing
  family Parent Portal payment, recurring or scheduled ePayments, a decline, a
  cancellation, a void/refund, receipts, family balances, and revenue reports.
  Coordinate with Jackrabbit and the payment partner because test payments may
  create real charges.
- Assign Jackrabbit permissions for the Executive Dashboard, customer records,
  transactions, Revenue Summary/Snapshot, Paid Fees, Deposit Slip, and Revenue
  Reconciliation reports according to each person's responsibilities.
- Accept that Django receives limited operational events and caches the public
  class feed, but has no Jackrabbit payment API or financial webhook sync. Its
  activity counts are coverage-limited and are not authoritative current
  customer totals. Balances, income, subscriptions, refunds, transaction status,
  and financial reporting remain in Jackrabbit.
- Supply approved privacy, payment terms, cancellation/refund, and data-retention
  policies before accepting live payments.
- **Approved legal baseline:** the client reports that its legal team approved
  the exact current Regular and Camp agreement wording. Verify the deployed
  canonical agreements match these approved identifiers before launch:

  - Regular: `waiver-system-b44ccb1-mainactivity-regular-v1`, SHA-256
    `e968971a67fc96279ffeaf96f43182e793377dfa1aea3feb621cd25c5c50506c`.
  - Camp: `waiver-system-b44ccb1-mainactivity-camp-v1`, SHA-256
    `587e76773817edcce0f4befb0018a328c82bea2c0b15f9436dc94d4d0668fef6`.

  The exact text and version identifiers must remain unchanged. Any text or
  version change requires renewed legal review before release, a new version,
  and corresponding documentation/test updates. Never alter a signed historical
  snapshot.
- Publish an owner/attorney-approved waiver privacy notice that identifies the
  categories collected, purpose, recipients, storage, access, retention,
  deletion/request process, and contact. Obtain appropriate consent for the
  collection and processing of a minor's identity and birthdate, guardian and
  emergency-contact details, medical information, and electronic signature.
  Enter its approved URL under **Homepage and business details > Online
  waiver**; the application must refuse to enable the public flow without it.
- Approve a waiver retention and deletion policy covering live database rows,
  immutable agreement snapshots, signatures, stored/downloaded PDFs, logs,
  local development copies, PostgreSQL dumps, off-site backups, restored
  environments, legal holds, corrections, and verified deletion requests.
- Confirm waiver data is protected in transit and encrypted at rest in the live
  database and every backup location. Signatures are stored privately in the
  database—not `/media`—and each waiver's validated PDF artifact is also stored
  in the database. PostgreSQL dumps therefore contain complete signed PDFs and
  highly sensitive minor, medical, guardian, and signature data. Limit and audit
  access to the live database, backup service, off-site storage, and
  staff-downloaded copies.
- Create a separate **Waiver Managers** approval list based on job duties. Test
  that this least-privilege role can review records and download protected PDFs
  but cannot edit website content, view unrelated reports, access Jackrabbit,
  or manage users. Define periodic staff-access and download/audit review,
  immediate offboarding, incident response, and escalation for inappropriate
  access.
- Approve the Returning-family verification risk. The public lookup requires
  exact gymnast date of birth, an exact case-insensitive surname match, and the
  last four digits of the parent/guardian phone number and is rate-limited;
  confirm negative/error responses do not disclose whether a record exists.
  Confirm that the match does not display or overwrite stored guardian,
  emergency-contact, medical, or pickup values; the signer must re-enter the
  current values for the new immutable snapshot.
  Treat this as an interim control and decide when to replace it with OTP, a
  one-time link, or authenticated guardian account verification.
- Run an owner-approved waiver end-to-end test on phone and desktop for all four
  paths: Regular/New, Regular/Returning, Camp/New, and Camp/Returning. Verify
  validation, a fresh signature, exact legal text/version, authoritative signing
  time, confirmation behavior, repeat/duplicate submission handling, returning
  search rate limiting, least-privilege staff visibility, a validated stored PDF
  whose exact bytes are returned on every download, agreement identifiers/hashes
  matching the approved baseline, unchanged historical snapshots,
  backup/restore, deletion/retention handling, and absence of public signature
  or PDF media URLs. Do not modify the approved agreement text as a test fixture.
- For an upgraded database with legacy signed waivers, confirm production
  startup runs `backfill_waiver_pdfs` after migrations, or run the command
  manually before staff depend on downloads. Verify every legacy record receives
  one validated stored PDF and that no existing artifact is replaced; investigate
  any validation failure instead of bypassing it.
- Keep **Show online waiver** off under **Homepage and business details > Online
  waiver** until the deployed agreements match the approved baseline and every
  privacy, consent, security, access, retention, backup, and end-to-end test
  above is complete. This toggle hides the homepage callout and navigation link
  and disables direct public access to `/online-waiver/`; existing staff-only
  records remain available. The feature is installed but disabled by default on
  fresh and upgraded deployments. Only after the remaining gates are complete
  should a Website Manager enter the approved **Privacy URL**, select **Show
  online waiver**, and save to enable the route, callout, and navigation link.
- Confirm the upper program age. Current pages conflict between age 17 and 18.
- Review and approve all manager-editable homepage text, contact details, links,
  SEO text, programs, highlights, social links, and section visibility before
  launch. Assign a staff owner responsible for keeping them current.
- Confirm current Open Gym eligibility, schedule, and price before publishing it.
- Confirm birthday-party days, times, packages, and pricing before publishing it.
- Replace or explicitly approve the generated hero photograph. It is illustrative
  and does not depict the Gyminators facility or staff.
- Provide a responsive, owner-approved real hero photo if available.
- Review old downloadable waivers and medication forms before retiring or
  migrating them; preserve records required by the approved retention policy
  and avoid presenting two conflicting agreement versions. Replacing the
  approved current text with language from a legacy form requires renewed legal
  review and a new version.
- Confirm the published office email and whether the fax number is still active.
- Assign new Django content editors to **Website Managers**, approved
  operational-report viewers to **Reporting Managers**, and approved waiver
  custodians to **Waiver Managers**. Combine groups only when one person truly
  needs multiple jobs. **Business Managers** is a legacy-compatible content
  group and should only retain existing assignments. These Django roles do not
  grant Jackrabbit access; financial-report permissions remain separate in
  Jackrabbit.
- Create separate Django website-admin and Jackrabbit accounts. Do not reuse or
  share passwords between Django, Jackrabbit owner/manager accounts, instructor
  Staff Portal accounts, or customer Parent Portal accounts. Rotate the initial
  Django administrator password before deployment.
- Review the administrator guide with every website manager. Verify access to
  the friendly content manager, and grant raw Django admin only when user or
  password administration is part of that person's responsibility.
- Decide whether Django content access and Jackrabbit operational/reporting
  access require MFA or an external identity provider.
- Configure encrypted off-site storage for both matching PostgreSQL dumps and
  uploaded-media archives, configure external uptime monitoring, and complete a
  documented test restore of both data stores. Confirm the `media_data` Docker
  volume is included and never run `docker compose down -v` in production.
  Treat the database dump as highly sensitive because it contains complete
  waiver records, private signatures, and stored signed PDFs in addition to the
  limited event ledger and cached class data. Restrict and audit backup access,
  test post-restore waiver permissions and exact PDF downloads, then test class
  refresh and Zapier event reconciliation.
