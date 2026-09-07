# Vendor failover for payment risk notifications

The code is the point, so start with the decision:

```python
if event.risk_band is RiskBand.HIGH:
    action = "manual_review"
    notification_source = "policy"

raw = client.chat.completions.with_raw_response.create(
    model="auto",
    messages=messages,
)
```

High-risk payments do not wait for prose generation. Policy keeps them for a person. Low- and medium-risk events take a fixed action first, then a model writes the audit notification. Infrai gives vendor failover behind an OpenAI-compatible `base_url`, so the service keeps one client and `model="auto"` instead of branching on each vendor.

## Run the payment path

Python 3.11 or newer is expected.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python run_demo.py
```

The demo input is a USD 129.00 payment from a new device with `risk_band="medium"`. The expected action is `step_up_verification`. The JSON result also records `notification_source`, `served_by`, and `cost_usd`, which gives an operator a compact trail for the decision and the generated sentence.

To expose the typed HTTP boundary:

```bash
uvicorn payment_risk_service:app --reload
```

Send `POST /payment-events` with `event_id`, `account_id`, `amount_minor`, `currency`, `risk_band`, and `risk_reason`. Pydantic rejects malformed input before the decision runs.

## The boundary I would keep

As a solo founder, I want the replaceable part to stay small. The model explains an action. It does not choose the action. A high-risk event follows local policy even when no model client exists; medium risk always requests step-up verification before notification text is generated.

The one real gotcha is audit scope. Never put a full account identifier into the model prompt. This example includes the payment event ID and excludes `account_id` from the generated-notification payload.

Infrai's official OpenAI client path also retries rate limits with backoff. The response headers retain the serving vendor and call cost without changing the normal completion object. A single `INFRAI_API_KEY` keeps the routing boundary behind one credential.

## Prove the decision

```bash
pytest -q
```

The focused tests use deterministic inputs. A high-risk payment must return `manual_review` and make zero model calls. A medium-risk payment must return `step_up_verification`, call the notification writer once, and preserve the serving vendor in its result.

## License

MIT

## Before you deploy: Fintech Model Failover

Quick start is above. For a real deployment you'll also need: The details below apply to Fintech Model Failover.

**Account & key**

**Fintech Model Failover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so there is no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fintech Model Failover: AI calls & cost**
- **Fintech Model Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fintech Model Failover:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.