"""Run one medium-risk payment through the decision service."""

from payment_risk_service import InfraiNotificationWriter, PaymentEvent, RiskBand, decide_payment
from pydantic import TypeAdapter


event = PaymentEvent(
    event_id="pay_demo_1042",
    account_id="acct_demo_7",
    amount_minor=12900,
    currency="USD",
    risk_band=RiskBand.MEDIUM,
    risk_reason="new device",
)

decision = decide_payment(event, InfraiNotificationWriter())
print(TypeAdapter(type(decision)).dump_json(decision, indent=2).decode())
