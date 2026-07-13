# Owner approval checklist

These items require business or legal decisions and cannot be safely inferred
from the current website.

Use this with the [administrator guide](ADMIN_GUIDE.md). Do not record passwords,
payment credentials, bank details, or Jackrabbit API keys in this checklist.

- Confirm whether the published `$60` annual registration and `$85 / $125 /
  $155` monthly tuition amounts remain current, then maintain the approved fees
  in Jackrabbit. Django does not maintain a second editable price catalog; its
  private reporting page only caches tuition published in Jackrabbit's public
  class feed.
- Confirm organization ID `154877`. Test Online Registration, Parent Portal,
  and the live class schedule from the public site. Test all five configured
  Jackrabbit destinations, including owner/manager and instructor Staff Portal,
  from the signed-in Django dashboard.
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
- Confirm the upper program age. Current pages conflict between age 17 and 18.
- Review and approve all manager-editable homepage text, contact details, links,
  SEO text, programs, highlights, social links, and section visibility before
  launch. Assign a staff owner responsible for keeping them current.
- Confirm current Open Gym eligibility, schedule, and price before publishing it.
- Confirm birthday-party days, times, packages, and pricing before publishing it.
- Replace or explicitly approve the generated hero photograph. It is illustrative
  and does not depict the Gyminators facility or staff.
- Provide a responsive, owner-approved real hero photo if available.
- Review old downloadable waivers and medication forms before migrating them.
- Confirm the published office email and whether the fax number is still active.
- Assign new Django content editors to **Website Managers** and approved
  operational-report viewers to **Reporting Managers**. Assign both groups only
  when a person needs both jobs. **Business Managers** is a legacy-compatible
  content group and should only retain existing assignments. These Django roles
  do not grant Jackrabbit access; financial-report permissions remain separate
  in Jackrabbit.
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
  volume is included and never run `docker compose down -v` in production. Treat
  the database dump as business-sensitive because it contains the limited event
  ledger and cached class data, and test post-restore class refresh and Zapier
  event reconciliation.
