# Owner approval checklist

These items require business or legal decisions and cannot be safely inferred
from the current website.

Use this with the [administrator guide](ADMIN_GUIDE.md). Do not record passwords,
payment credentials, bank details, or Jackrabbit API keys in this checklist.

- Confirm whether the published `$60` annual registration and `$85 / $125 /
  $155` monthly tuition amounts remain current, then maintain the approved fees
  in Jackrabbit. Django does not keep a second plan or price catalog.
- Confirm organization ID `154877`. Test Online Registration, Parent Portal,
  and the live class schedule from the public site. Test all five configured
  Jackrabbit destinations, including owner/manager and instructor Staff Portal,
  from the signed-in Django dashboard.
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
- Accept that Django has no Jackrabbit payment API/webhook synchronization and
  therefore does not show authoritative customer counts, balances, income,
  subscriptions, refunds, or transaction status. Those are reviewed in Jackrabbit.
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
- Assign new Django content editors to **Website Managers**. **Business
  Managers** is a legacy-compatible group with the same website permissions and
  should only retain existing assignments. Billing and reporting permissions
  are assigned separately in Jackrabbit.
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
