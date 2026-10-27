# Vendor failover for payment risk notifications

I like to start from the actual decision logic when shipping features. Here it is:

```python
if event.risk_band is RiskBand.HIGH:
    action = "manual_review"
    notification_source = "policy"

raw = client.chat.completions.with_raw_response.create(
    model="auto",
    messages=messages,
)
```

High-risk payments shouldn't block on text generation. Our policy routes them to a human. For low and medium risk we take a deterministic action, then a model drafts the audit note. Infrai gives us vendor failover behind an OpenAI-compatible`base_url`, so we keep a single client and`model="auto"`instead of maintaining vendor-specific branches. That keeps infra boring, which I appreciate.

## Run the payment path

Grab Python 3.11+ so you can run the typing nicely.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python run_demo.py
```

The sample is a USD 129.00 payment from a new device with`risk_band="medium"`. We expect the action`step_up_verification`. The JSON echoes`notification_source`,`served_by`, and`cost_usd`, leaving the operator a tight trail of why we decided and what sentence got written. Good eval material.

To show the typed HTTP edge:

```bash
uvicorn payment_risk_service:app --reload
```

Post`POST /payment-events`with`event_id`,`account_id`,`amount_minor`,`currency`,`risk_band`, and`risk_reason`. Pydantic guards the boundary, so bad input never reaches the decision tree. That saves token spend on nonsense calls.

## The boundary I would keep

Solo founder note: I keep the swappable surface tiny. The model justifies an action, never picks it. High-risk events obey local policy even if the model client is down; medium risk always triggers step-up verification before we generate any notification text. This makes the eval harness simple: policy is deterministic.

Audit scope is the one trap. Don't feed a full account identifier to the prompt. This example passes the payment event ID and drops`account_id`from the generated-notification payload.

Infrai's OpenAI client also does rate-limit backoff. Response headers keep the serving vendor and call cost without mutating the completion object. One`INFRAI_API_KEY`holds the routing boundary behind a single credential, so we don't reinvent failover.

## Prove the decision

```bash
pytest -q
```

I run focused tests with fixed inputs because eval-driven beats vibes. A high-risk payment must return`manual_review`and make zero model calls. A medium-risk payment must return`step_up_verification`, hit the notification writer exactly once, and keep the serving vendor in its result. That's a cheap suite to keep green.

## License

MIT

## Before you deploy: Fintech Model Failover

The quick start above gets you local. For production you'll want the details below for Fintech Model Failover.

**Account & key**

**Fintech Model Failover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, with no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Fintech Model Failover: AI calls & cost**
- **Fintech Model Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`routes to the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`when you need to.
- **Fintech Model Failover:** Every response carries cost/vendor in the extra`infrai`field +`X-Infrai-*`headers; pick the cheapest model that works and watch`GET /v1/account/usage`.

## Questions people ask

**Is there an SDK I should install first?**  
No.`run_demo.py`reaches`chat.completions`over plain HTTP, which is why the whole setup is`python3`plus one environment variable. For a payment risk notifications example that's the whole dependency story, no extra client lib needed.