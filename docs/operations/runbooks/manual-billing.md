# Manual billing pipeline for early design partners

This runbook defines a **manual, metrics-driven billing pipeline** for early paying
customers. It uses the in-process metrics subsystem and the `/api/metrics/*`
endpoints to export per-tenant usage over a billing period and aggregate it
into invoice-ready summaries.

The pipeline is intentionally simple and does **not** integrate with any payment
processor. Operators run it on a fixed schedule (for example, once per month),
review the exported CSV/JSON, and then generate invoices manually in their
preferred accounting system.

## 1. Scope and data sources

The pipeline relies on the following internal metrics recorded by
`MetricsService` ([`src/neuroca/core/services/metrics.py`](src/neuroca/core/services/metrics.py)):

- `usage.llm.calls` &mdash; total LLM calls per tenant, user, provider, model.
- `usage.llm.tokens.prompt` &mdash; prompt tokens per tenant, user, provider, model.
- `usage.llm.tokens.completion` &mdash; completion tokens per tenant, user, provider, model.
- `usage.llm.tokens.total` &mdash; total tokens per tenant, user, provider, model.
- `usage.memory.operations.create` &mdash; memory create operations per tenant, user, tier.
- `usage.memory.operations.read` &mdash; memory read operations per tenant, user, tier.
- `usage.memory.operations.update` &mdash; memory update operations per tenant, user, tier.
- `usage.memory.operations.delete` &mdash; memory delete operations per tenant, user, tier.
- `usage.memory.storage.bytes` &mdash; approximate storage footprint per tenant and tier.

These metrics are available via the public metrics API surface:

- `GET /api/metrics/data/{name}` (see [`docs/pages/api/endpoints.md`](docs/pages/api/endpoints.md))

## 2. Prerequisites

- Neuroca API is running and reachable (for example, `http://127.0.0.1:8000`).
- You have an **admin** or **operator** API key or authentication mechanism
  that allows access to `/api/metrics/*` endpoints.
- You know the list of **tenants** you intend to bill (for example, from your
  auth/tenant database or configuration).
- Optional but recommended: `python3` and the `requests` library installed in
  your operator environment:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install requests
  ```

## 3. Choosing a billing period

For early design partners, a **calendar month** is usually sufficient.

Define:

- `period_start` &mdash; inclusive start timestamp (ISO 8601), e.g.:

  ```text
  2025-12-01T00:00:00Z
  ```

- `period_end` &mdash; exclusive end timestamp (ISO 8601), e.g.:

  ```text
  2026-01-01T00:00:00Z
  ```

You will pass these timestamps as `start_time` / `end_time` query parameters
to the metrics endpoints.

## 4. Querying metrics per tenant

The metrics routes support **label-based filtering** via the `labels` query
parameter, which FastAPI maps from `labels.<key>=<value>` query pairs.

For example, to fetch `usage.llm.calls` for tenant `acme-corp` over a billing
period:

```bash
curl -sS \
  "http://127.0.0.1:8000/api/metrics/data/usage.llm.calls\
?start_time=2025-12-01T00:00:00Z\
&end_time=2026-01-01T00:00:00Z\
&labels.tenant_id=acme-corp"
```

Response shape (simplified):

```json
{
  "name": "usage.llm.calls",
  "unit": "count",
  "points": [
    {"timestamp": "2025-12-10T12:34:56.123456", "value": 3.0},
    {"timestamp": "2025-12-20T09:01:02.345678", "value": 5.0}
  ]
}
```

To compute the **total** usage for that period you sum the `value` fields in
`points`.

The same pattern applies to all usage metrics, changing only the metric name
and labels:

- LLM tokens:
  - `usage.llm.tokens.prompt`
  - `usage.llm.tokens.completion`
  - `usage.llm.tokens.total`
- Memory operations:
  - `usage.memory.operations.create`
  - `usage.memory.operations.update`
  - `usage.memory.operations.delete`
- Storage footprint:
  - `usage.memory.storage.bytes` (gauge; last point in the period is a good
    approximation of end-of-period storage).

For metrics with additional labels (for example, `user_id`, `provider`, `tier`)
you can either:

- Filter down to a specific combination (for example, per-tenant-per-model),
  or
- Omit those labels and treat all samples for the tenant as a single pool.

For early design partners a **per-tenant aggregate** is usually enough.

## 5. Example aggregation script (Python)

The following Python script demonstrates how to:

1. Iterate over a list of tenants.
2. Query the usage metrics for each tenant over a billing period.
3. Aggregate them into a CSV file suitable for invoicing.

```python
import csv
import os
from datetime import datetime

import requests

API_BASE = os.environ.get("NEUROCA_API_BASE", "http://127.0.0.1:8000")
API_KEY = os.environ.get("NEUROCA_API_KEY")  # if you use API key auth

TENANTS = ["acme-corp", "contoso", "internal-demo"]
PERIOD_START = "2025-12-01T00:00:00Z"
PERIOD_END = "2026-01-01T00:00:00Z"

METRICS = [
    "usage.llm.calls",
    "usage.llm.tokens.total",
    "usage.memory.operations.create",
    "usage.memory.operations.update",
    "usage.memory.operations.delete",
]

def _headers() -> dict:
    headers: dict[str, str] = {"Accept": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers

def _sum_metric(name: str, tenant_id: str) -> float:
    url = f"{API_BASE}/api/metrics/data/{name}"
    params = {
        "start_time": PERIOD_START,
        "end_time": PERIOD_END,
        "labels.tenant_id": tenant_id,
        "limit": 10000,
    }
    resp = requests.get(url, params=params, headers=_headers(), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return sum(float(point["value"]) for point in data.get("points", []))

def main() -> None:
    rows = []
    for tenant in TENANTS:
        usage = {}
        for metric in METRICS:
            usage[metric] = _sum_metric(metric, tenant)
        rows.append(
            {
                "tenant_id": tenant,
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "llm_calls": usage["usage.llm.calls"],
                "llm_tokens": usage["usage.llm.tokens.total"],
                "memory_creates": usage["usage.memory.operations.create"],
                "memory_updates": usage["usage.memory.operations.update"],
                "memory_deletes": usage["usage.memory.operations.delete"],
            }
        )

    filename = f"billing_usage_{PERIOD_START}_{PERIOD_END}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "tenant_id",
                "period_start",
                "period_end",
                "llm_calls",
                "llm_tokens",
                "memory_creates",
                "memory_updates",
                "memory_deletes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} tenant rows to {filename}")

if __name__ == "__main__":
    main()
```

This script intentionally:

- Uses only the public `/api/metrics/data/{name}` endpoint.
- Aggregates usage **per tenant per period** into a flat CSV.
- Leaves pricing and invoice generation to your external tooling.

## 6. Mapping usage to pricing

Pricing is **out of scope** for the codebase, but a reasonable first pass for
design partners is:

- LLM usage:
  - Charge per **1,000 total tokens** (for example, `$0.15 / 1k tokens`).
  - Optionally include a lower-priced tier for on-prem or GPU-backed tenants.
- Memory usage:
  - Charge per **memory write** (create/update/delete), or
  - Charge per **GiB-month** of `usage.memory.storage.bytes` (approximated by
    the end-of-period gauge value).

The exported CSV can be loaded into a spreadsheet or billing system where you
define formulas such as:

```text
llm_cost = llm_tokens / 1000 * 0.15
memory_op_cost = (memory_creates + memory_updates + memory_deletes) * 0.0005
total_cost = llm_cost + memory_op_cost
```

## 7. Validation checklist

Before sending invoices for a new billing period:

- [ ] Confirm that `usage.*` metrics exist and are non-empty for at least one
      tenant during the period.
- [ ] Run the export script and spot-check:
  - [ ] A tenant with known heavy usage.
  - [ ] A tenant with little or no usage.
- [ ] Compare token and call counts against:
  - [ ] LLM provider dashboards (if available).
  - [ ] Internal logs for a small random sample of requests.
- [ ] Archive the generated CSV and any derived invoice artifacts in your
      usual accounting or S3 bucket.

Once this checklist passes for at least one full cycle, you can promote this
pipeline to your regular monthly operations runbook.