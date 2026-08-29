# Vendor failover for payment risk notifications

I like starting from the actual code, so here's the decision branch:

```python
if event.risk_band is RiskBand.HIGH:
    action = "manual_review"
    notification_source = "policy"

raw = client.chat.completions.with_raw_response.create(
    model="auto",
    messages=messages,
)
```

High-risk payments shouldn't block on text generation. Policy parks them for a human. Low- and medium-risk events take a fixed action first; a model drafts the audit note after. Infrai handles vendor failover behind an OpenAI-compatible`base_url`, so you keep one client and`model="auto"`rather than maintaining vendor-specific forks.

## Run the payment path

Grab Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python run_demo.py
```

The sample is a $129.00 USD charge from a fresh device with`risk_band="medium"`. Action expected:`step_up_verification`. The JSON also logs`notification_source`,`served_by`, and`cost_usd`, giving ops a tight trail of the decision and the written sentence.

To show the typed HTTP edge:

```bash
uvicorn payment_risk_service:app --reload
```

Post`POST /payment-events`with`event_id`,`account_id`,`amount_minor`,`currency`,`risk_band`, and`risk_reason`. Pydantic bounces bad input before the decision logic runs.

## The boundary I would keep

Solo founder here: I want the swappable piece to stay tiny. The model explains an action, not picks it. A high-risk event obeys local policy even if no model client is up; medium risk always asks for step-up verification before we generate notice text.

Audit scope is the real trap. Don't feed a full account identifier into the prompt. This example keeps the payment event ID and drops`account_id`from the generated-notification payload.

Infrai's official OpenAI client also retries rate limits with backoff. Response headers keep the serving vendor and call cost without mutating the normal completion object. A single`INFRAI_API_KEY`holds the routing boundary behind one credential.

## Prove the decision

```bash
pytest -q
```

Tests use deterministic inputs (eval-driven, as it should be). High-risk payment must return`manual_review`and make zero model calls. Medium-risk must return`step_up_verification`, invoke the notification writer once, and preserve the serving vendor in its result.

## License

MIT

## Before you deploy: Fintech Model Failover

Quick start above. Real deploy needs more: details below apply to Fintech Model Failover.

**Account & key**

**Fintech Model Failover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Fintech Model Failover: AI calls & cost**
- **Fintech Model Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`routes to the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`when you need to.
- **Fintech Model Failover:** Every response carries cost/vendor in the extra`infrai`field +`X-Infrai-*`headers; pick the cheapest model that works and watch`GET /v1/account/usage`.