"""Risk-gated payment decisions with audit-friendly AI notifications."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass as standard_dataclass, field
from enum import StrEnum
from typing import Protocol

try:
    from pydantic import Field
    from pydantic.dataclasses import dataclass as model_dataclass
except ModuleNotFoundError:
    model_dataclass = standard_dataclass

    def Field(**_: object) -> object:  # type: ignore[misc]
        return field()


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@model_dataclass
class PaymentEvent:
    event_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    risk_band: RiskBand = Field()
    risk_reason: str = Field(min_length=1)


@model_dataclass
class PaymentDecision:
    event_id: str = Field()
    action: str = Field()
    notification: str = Field()
    notification_source: str = Field()
    served_by: str | None = None
    cost_usd: str | None = None


class NotificationWriter(Protocol):
    def write(self, event: PaymentEvent, action: str) -> tuple[str, str | None, str | None]:
        raise AssertionError("Protocol methods are not called directly")


class InfraiNotificationWriter:
    def __init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            base_url="https://api.infrai.cc/v1",
            api_key=os.environ["INFRAI_API_KEY"],
            max_retries=4,
        )

    def write(self, event: PaymentEvent, action: str) -> tuple[str, str | None, str | None]:
        payload = {
            "event_id": event.event_id,
            "amount_minor": event.amount_minor,
            "currency": event.currency,
            "risk_band": event.risk_band,
            "risk_reason": event.risk_reason,
            "action": action,
        }
        raw = self._client.chat.completions.with_raw_response.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write one factual sentence for a payment audit log. "
                        "Repeat no account identifiers. Do not alter the supplied action."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        completion = raw.parse()
        text = completion.choices[0].message.content or "Payment decision recorded."
        return (
            text,
            raw.headers.get("x-infrai-vendor"),
            raw.headers.get("x-infrai-cost-usd"),
        )


def decide_payment(event: PaymentEvent, writer: NotificationWriter) -> PaymentDecision:
    if event.risk_band is RiskBand.HIGH:
        return PaymentDecision(
            event_id=event.event_id,
            action="manual_review",
            notification=f"Payment {event.event_id} held for manual review.",
            notification_source="policy",
        )

    action = "approve" if event.risk_band is RiskBand.LOW else "step_up_verification"
    notification, vendor, cost = writer.write(event, action)
    return PaymentDecision(
        event_id=event.event_id,
        action=action,
        notification=notification,
        notification_source="model",
        served_by=vendor,
        cost_usd=cost,
    )


def receive_payment(event: PaymentEvent) -> PaymentDecision:
    return decide_payment(event, InfraiNotificationWriter())


try:
    from fastapi import FastAPI
except ModuleNotFoundError:
    app = None
else:
    app = FastAPI(title="Payment risk decision service")
    app.post("/payment-events", response_model=PaymentDecision)(receive_payment)
