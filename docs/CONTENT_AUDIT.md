# Gyminators live-site content audit

Verified July 10, 2026 against `https://www.gyminators.com/`.
Reporting implementation notes updated July 13, 2026.

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
- The public class-schedule link uses Jackrabbit's hosted live listings. The
  private report page also caches the public class feed for search, schedule,
  openings, waitlist/full status, and published-tuition reporting; Jackrabbit
  remains authoritative and the cached copy may be delayed.
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

## Deliberately excluded or still provisional

- Program age pages conflict between upper ages 17 and 18. The current local
  draft uses 17 in its general age range, hero proof point, and Recreational
  program while awaiting explicit owner confirmation.
- Event pages contain schedules/prices that may change and instruct families to
  call for availability.
- Birthday timing conflicts between pages.
- Upcoming/competition pages contain dated April 2026 flyers.
- Linked medication and waiver forms appear old and require legal/owner review.
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
