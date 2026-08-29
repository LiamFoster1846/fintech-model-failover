from payment_risk_service import PaymentEvent, RiskBand, decide_payment


class RecordingWriter:
    def __init__(self) -> None:
        self.calls = 0

    def write(self, event: PaymentEvent, action: str) -> tuple[str, str, str]:
        self.calls += 1
        return f"Recorded {event.event_id}: {action}.", "vendor-a", "0.001"


def test_high_risk_payment_requires_review_without_model_call() -> None:
    writer = RecordingWriter()
    event = PaymentEvent(
        event_id="pay_9001",
        account_id="acct_42",
        amount_minor=250000,
        currency="USD",
        risk_band=RiskBand.HIGH,
        risk_reason="velocity threshold exceeded",
    )

    decision = decide_payment(event, writer)

    assert decision.action == "manual_review"
    assert decision.notification_source == "policy"
    assert writer.calls == 0


def test_medium_risk_payment_uses_model_only_for_notification() -> None:
    writer = RecordingWriter()
    event = PaymentEvent(
        event_id="pay_9002",
        account_id="acct_43",
        amount_minor=12900,
        currency="USD",
        risk_band=RiskBand.MEDIUM,
        risk_reason="new device",
    )

    decision = decide_payment(event, writer)

    assert decision.action == "step_up_verification"
    assert decision.notification == "Recorded pay_9002: step_up_verification."
    assert decision.served_by == "vendor-a"
    assert writer.calls == 1
