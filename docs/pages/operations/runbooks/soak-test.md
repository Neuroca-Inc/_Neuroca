# Soak Test Runbook (Pre‑GA)

This runbook describes how to run a multi‑day soak test of the Neuroca memory system with a coding agent to validate stability, consolidation/decay, and long‑horizon recall.

## Objectives

- Validate that the agent remains healthy over days (no crash loops, stable latency)
- Observe STM→MTM→LTM promotions, decay, and context injection behavior
- Confirm backup/restore integrity while the system is live
- Establish baseline metrics (promotions/sec, backlog age, failures)

## Prerequisites

- Docker and docker‑compose
- OPENAI_API_KEY (or configure a local provider like Ollama)

## Start the system

```bash
# Build and run Neuroca with Postgres
docker compose -f docker-compose.agent.yml up -d --build

# Verify health
curl -sf http://localhost:8000/health
```

## Agent traffic

- Wire your coding agent to the Neuroca API; send realistic prompts, file diffs, and tasks.
- Optional: For short demos, accelerate consolidation by overriding intervals via env.

## Operational tips

- Manual maintenance during a demo: in the LLM demo, use `/maint` then `/stats` to see tier counts move.
- Fast‑tiers demo mode: run `python scripts/test_memory_with_llm.py --fast-tiers` to exercise promotions quickly.
- Curated context: by default, the full app uses the context injector to send “current + precise context,” not the entire transcript.

## Backup/restore checks

- Nightly DB backup (psql/pg_dump) and periodic test restore in a scratch DB.
- Validate that seeded memories and promoted semantic facts reappear after restore.

## Metrics/alerts (optional)

- Enable the Prometheus exporter in production config and scrape `memory_*` metrics (promotion rates, backlog age, failures).

## Pass criteria

- No container crash loops or repeated 5xx in logs
- Promotions and decays occur at expected cadence; backlog age remains bounded
- After hours/days, asking for stable project preferences still retrieves correct facts without whole‑transcript injection
- Backup/restore produces a consistent state

```text
If stable after several days, promote version from 1.0.0‑rc1 to 1.0.0 and publish.
```
