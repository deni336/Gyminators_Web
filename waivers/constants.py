"""Canonical agreement copy ported from the Android waiver application.

IMPORTANT: This text is a faithful snapshot of the constants in
``MainActivity.kt`` from deni336/Waiver_system. The client reports that its
legal team approved these exact Regular and Camp versions. Treat both strings
as version-locked: any wording change requires a new version, hash, and legal
review before use.
"""

from dataclasses import dataclass
import hashlib
from textwrap import dedent


REGULAR = "regular"
CAMP = "camp"

REGULAR_AGREEMENT_VERSION = "waiver-system-b44ccb1-mainactivity-regular-v1"
CAMP_AGREEMENT_VERSION = "waiver-system-b44ccb1-mainactivity-camp-v1"

REGULAR_AGREEMENT_TEXT = dedent(
    """
    ATHLETE MEMBERSHIP AGREEMENT AND INFORMATION

    Read the following carefully. Initial each numbered statement and sign below.

    Agreement: In consideration of my membership in Gyminators Gymnastics & Tumbling, Inc., and my participation in Gyminators Gymnastics & Tumbling, Inc. classes, events, competitions, and activities, I agree to be bound by each of the following:

    1. Eligibility: I agree to comply with the rules of Gyminators Gymnastics & Tumbling, Inc.

    2. Readiness to Participate: I will only participate in those Gyminators Gymnastics & Tumbling, Inc. classes, events, competitions, and activities for which I believe my child is physically and psychologically prepared. Prior to participation, my child will have practiced their exercises and will perform only those exercises which they have accomplished to the degree of confidence necessary to assure they can perform them by themselves, and without injury.

    3. Medical Attention: I give my consent to Gyminators Gymnastics & Tumbling, Inc. to provide, through a medical staff of its choice, customary medical/athletic training attention, transportation, and emergency medical services as warranted in the course of my child's participation.

    4. Waiver and Release: I am fully aware of and accept the risks, including the risk of catastrophic injury, paralysis, and even death, as well as other damages and losses associated with participation in gymnastics activities and events. I further agree that Gyminators Gymnastics & Tumbling, Inc., any sponsor of a Gyminators event, and the employees, agents, officers, and directors of these organizations shall not be liable for any losses or damages occurring as a result of my child's participation in the event, except where such loss or damage is the result of intentional or reckless conduct.

    5. Withdrawals: Withdrawal notices will be accepted and must be received at least thirty (30) days prior to the beginning of the following month. It is my responsibility to pay the full balance of tuition and fees due.

    6. Payments: Payments are due on or before the 25th of each month. Late fees will be applied to all accounts not current by the 1st of each month.

    7. Registration fees: Registration fees are due annually. I understand it is my responsibility to pay this annually, and if I started in the middle of the year my next registration fee will be prorated.

    By signing, I also consent that Gyminators Gymnastics & Tumbling may use photographs of my child in promotional ads and publications.
    """
).strip()

CAMP_AGREEMENT_TEXT = dedent(
    """
    CAMP ENROLLMENT & AGREEMENT FORM

    By enrolling my child in the above stated Activity, I agree to each of the following:

    1. I will be responsible for sending or purchasing an adequate lunch for my child(ren). A mid-afternoon snack will be provided by the facility. I may send money if my child wishes to purchase extra drinks, candies, etc.

    2. I will be responsible for immediately picking up my child(ren) should their conduct be deemed inappropriate and/or irresponsible, causing unsafe acts or conditions toward themselves or others. I further understand that in such an event, no refunds will be issued.

    3. I will provide transportation for my child(ren) and agree to drop off not earlier than 8:45am and pick up no later than 3:15pm. If scheduled for extended day, drop off is not earlier than 7:00am and pick up is no later than 6:00pm. If I am late, I understand I will be charged $1.00 per minute I am not there past 6:00pm.

    CAMP WAIVER & CONSENT FORM

    Please read carefully. You will be waiving and releasing any and all claims for injuries your child(ren) might sustain from their participation in the Activity stated above.

    I recognize and acknowledge that there are certain risks of injury to those attending and/or participating in the above activity. I assume the full risk of any such injuries, damages, or loss, regardless of severity.

    I release and discharge Gyminators Gymnastics and Tumbling, Inc. and their agents, directors, officers, successors, and/or employees from liability arising from my child's attendance at or participation in the Activity. I agree to indemnify and hold harmless Gyminators Gymnastics & Tumbling and their agents, directors, officers, successors, and/or employees from injuries, damages, claims, and courses of action associated with the Activity.

    I understand that my personal health and accident insurance are my sole financial protection in the event of injury during the Activity. I affirm that the statements set forth above are true and correct, and by my signature agree to them accordingly.
    """
).strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Agreement:
    enrollment_type: str
    title: str
    version: str
    text: str
    clause_count: int
    sha256: str


AGREEMENTS = {
    REGULAR: Agreement(
        enrollment_type=REGULAR,
        title="Regular enrollment",
        version=REGULAR_AGREEMENT_VERSION,
        text=REGULAR_AGREEMENT_TEXT,
        clause_count=7,
        sha256=sha256_text(REGULAR_AGREEMENT_TEXT),
    ),
    CAMP: Agreement(
        enrollment_type=CAMP,
        title="Camp enrollment",
        version=CAMP_AGREEMENT_VERSION,
        text=CAMP_AGREEMENT_TEXT,
        clause_count=3,
        sha256=sha256_text(CAMP_AGREEMENT_TEXT),
    ),
}


def get_agreement(enrollment_type: str) -> Agreement:
    try:
        return AGREEMENTS[enrollment_type]
    except KeyError as exc:
        raise ValueError("Unknown enrollment type.") from exc
