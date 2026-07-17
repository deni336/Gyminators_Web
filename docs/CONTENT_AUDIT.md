# Gyminators live-site content audit

Verified July 10, 2026 against `https://www.gyminators.com/`.
Reporting implementation notes updated July 13, 2026.
Online-waiver source notes updated July 16, 2026.

This is a point-in-time content record, not a substitute for owner approval.
Recheck prices, schedules, staff credentials, program ages, policies, and all
external links before launch. Editors should use the
[administrator guide](ADMIN_GUIDE.md) when applying approved corrections.

## Confirmed and reflected locally

- Opened in May 2003.
- Address: 4603 Shirley Ave, Jacksonville, FL 32210.
- Phone: (904) 388-5533.
- Parent & Tot: walking through age 3.
- Preschool: ages 2½ through 5.
- Recreational program begins at age 5.
- Fully air-conditioned facility.
- USA Gymnastics and AAU membership.
- Programs include Parent & Tot, Preschool, Recreational, Pre-Team / Hot Shots,
  Competitive Team, Tumbling, Hip-Hop Dance, Boys Gymnastics, Ninja Warriors,
  and Fit, Flex, Fun.
- Open Gym, Summer Camp, and Birthday Parties are offered.
- Key staff—not necessarily every instructor—hold USAG Safety, CPR, and First
  Aid certifications, with ongoing staff training.
- Current Jackrabbit registration and Parent Portal links return HTTP 200.

## Jackrabbit workflow reflected locally

- Django is the marketing website and owner-editable content manager. It does
  not process payments or keep authoritative customer or transaction records.
- The private reporting dashboard stores a privacy-minimized operational event
  ledger: approved event types and timestamps, optional location, and opaque
  Jackrabbit family/contact/student/class/enrollment identifiers. It rejects
  names, contact details, birthdates, notes, balances, financial data, and raw
  Zapier payloads.
- New families are sent to Jackrabbit Online Registration.
- Existing families are sent to the Jackrabbit Parent Portal for enrollment,
  balances, billing information, and payments.
- The public `/class-schedule/` page and private report page use the same cached
  Jackrabbit public feed for search, schedule, openings, waitlist/full status,
  and published-tuition reporting. They show only classes whose published start
  year is the current or next calendar year. Individual class actions open the
  corresponding Jackrabbit-hosted registration or waitlist page; the general
  Jackrabbit listing remains a signed-in manager reference rather than a public
  website destination. Jackrabbit remains authoritative and the cached copy may
  be delayed.
- The private Django dashboard links authorized personnel to the separate
  Jackrabbit owner/manager login and instructor Staff Portal.
- Django reports the approved non-financial signals: new family/contact/student/
  lead records, enrollments and drops, waitlist activity, inactive-student
  signals, and public class listings. Coverage begins with each Zap or approved
  backfill and therefore is not an authoritative current customer total.
- Financial reporting remains in Jackrabbit. No payment API or financial webhook
  synchronization with Django is configured, and published tuition is not
  revenue.

## Published financial information requiring owner confirmation

The live Getting Started page currently shows:

- $60 annual registration, including a Gyminators T-shirt.
- $85/month for one class per week.
- $125/month for two classes per week.
- $155/month for three classes per week.
- Tuition due on or before the 25th and late after the 2nd.

These values were not seeded into editable Django content because Jackrabbit is
the authoritative source for class tuition, registration fees, account balances,
and payment processing. The reporting cache may display tuition that Jackrabbit
publishes for an individual class, but it is not an editable price catalog or
income calculation. The owner must confirm and configure prices in Jackrabbit
before launch.

## Online waiver source and approved legal baseline

The public `/online-waiver/` workflow adapts the Regular/Camp and New/Returning
branching from
[deni336/Waiver_system at inspected commit `b44ccb1`](https://github.com/deni336/Waiver_system/tree/b44ccb132f0fe6cbd46f5ffa0aff697f183b89aa),
used under the MIT License, Copyright (c) 2026 deni336. The project
[license](../LICENSE) retains that notice; the attribution and license notice
must remain with redistributed copies of the adapted feature.

The client reports that its legal team approved the exact current agreement
wording. The locked baseline is Regular version
`waiver-system-b44ccb1-mainactivity-regular-v1` (SHA-256
`e968971a67fc96279ffeaf96f43182e793377dfa1aea3feb621cd25c5c50506c`) and
Camp version `waiver-system-b44ccb1-mainactivity-camp-v1` (SHA-256
`587e76773817edcce0f4befb0018a328c82bea2c0b15f9436dc94d4d0668fef6`).
The exact text and version identifiers must remain unchanged. Any text or
version change requires renewed legal review before release and a new version;
it must never rewrite a signed historical snapshot.

This approval covers the agreement wording, not the separate privacy notice,
minor/medical/signature-data consent, retention/deletion, security, access,
backup, or end-to-end launch decisions. Existing signed records preserve an
immutable versioned signed-agreement snapshot plus one validated, immutable PDF
artifact in the database. Authorized downloads return the exact stored PDF bytes
rather than regenerating the document.

Until the remaining privacy, consent, retention, security, access, backup, and
end-to-end checks are complete, a Website Manager keeps **Show online waiver**
off under **Homepage and business details > Online waiver**. This hides the
navigation link and homepage callout and disables direct public access to
`/online-waiver/`; existing staff-only records remain available. Fresh and
upgraded deployments install the feature disabled by default. After the
remaining gates are complete, a Website Manager enters the approved Privacy
URL, selects **Show online waiver**, and saves. Without both values the public
route and promotions remain unavailable.

## Deliberately excluded or still provisional

- Program age pages conflict between upper ages 17 and 18. The current local
  draft uses 17 in its general age range, hero proof point, and Recreational
  program while awaiting explicit owner confirmation.
- Event pages contain schedules/prices that may change and instruct families to
  call for availability.
- Birthday timing conflicts between pages.
- Upcoming/competition pages contain dated April 2026 flyers.
- Linked medication and legacy waiver forms appear old. Reconcile or retire them
  without replacing the approved current text. Any text/version replacement
  requires renewed legal review before release so families do not see
  conflicting agreements.
- The source homepage repeats program and trial content; the redesign keeps one
  concise version of each.

## Sources

- Home: https://www.gyminators.com/
- About: https://www.gyminators.com/about-gyminators/about-gyminators-gymnastics
- Staff: https://www.gyminators.com/about-gyminators/gyminators-staff
- Getting Started/pricing: https://www.gyminators.com/membership/first-class
- Preschool: https://www.gyminators.com/programs/preschool
- Parent & Tot: https://www.gyminators.com/programs/parents-a-tots
- Contact: https://www.gyminators.com/contact-us
- Open Gym: https://www.gyminators.com/camp-events/open-gym
- Birthday Parties: https://www.gyminators.com/camp-events/parties

## Jackrabbit implementation references

- Local nine-feed setup and privacy rules:
  [Jackrabbit Zapier setup](JACKRABBIT_ZAPIER_SETUP.md)
- Online Registration: https://help.jackrabbitclass.com/help/online-web-reg
- Parent Portal: https://help.jackrabbitclass.com/help/parent-portal
- Require payment in the Parent Portal:
  https://help.jackrabbitclass.com/help/require-payment-parent-portal
- Set up ePayments: https://help.jackrabbitclass.com/help/set-up-epayments
- Online class listings:
  https://help.jackrabbitclass.com/help/online-class-listings
- Revenue reports: https://help.jackrabbitclass.com/help/revenue-reports
