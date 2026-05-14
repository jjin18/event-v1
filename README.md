# surplus-match

The matching algorithm that powers [surplus](https://app.surpluslayer.com).
Self-contained Python library — no FastAPI, no UI, no deployment artifacts.
This branch (`surplus-match-library`) is the algorithm extracted from
`event-v1`'s `event-match/` subdirectory and promoted to the repo root.

## What it does

Given a CSV of event attendees with LinkedIn / X / GitHub handles, it:

1. **Enriches** each person from public signal (GitHub API + Claude with web_search)
2. **Synthesizes** an event-specific scoring rubric via an LLM
3. **Scores** every pair on shared context + complementary value
4. **Ranks** top-K matches per person and flags mutuals (both top-K each other)
5. **Explains** each pair with an LLM-generated rationale + draftable intro message

All output is plain JSON. Caching is file-based (`.cache/`) and gitignored.

## Layout

```
packages/
  schema.py    Person, EnrichedPerson dataclasses
  ingest.py    CSV → list[Person]
  enrich.py    Person → EnrichedPerson  (LLM + web_search)
  github.py    GitHub API helpers
  rubric.py    (event_name, desc, people) → custom weight rubric
  score.py     pair scoring math
  matrix.py    top_k_per_person + mutual matches
  explain.py   pair → rationale + intro_message
  run.py       orchestrator (also a CLI)
  shared/cache.py   file-based LLM call cache
prompts/
  enrich_system.md
  rubric_synthesis.md
  explain_match.md
requirements.txt
```

## Quick start

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...   # optional but recommended

python -m packages.run path/to/guests.csv \
  --name "AI Founders Dinner" \
  --desc "Small dinner for founders building agent infra in SF."
```

Output: `data/matches/<event_id>/matrix.json` plus a console summary.

## As a library

```python
from packages.run import run_pipeline

matrix, by_id, rubric = await run_pipeline(
    "guests.csv",
    event_name="AI Founders Dinner",
    event_description="...",
    enrich_concurrency=100,
    explain_mode="lazy",  # or "upfront" to generate all rationales eagerly
)
```

`matrix` is a dict with `people`, `pairs`, `top_k_per_person`, `mutual_pairs`,
`stats`. `by_id` is `dict[person_id → EnrichedPerson]`. `rubric` is the
event-specific scoring config the LLM synthesized.

## Caching

- `.cache/enrich/<hash>.json` — per-person enrichment results
- `.cache/rubric_match/<hash>.json` — per-event rubric
- `.cache/rationale/<hash>.json` — per-pair rationale + intro

All keyed by content hash + model version, so model upgrades invalidate cleanly.

## Cost reference (Anthropic Haiku 4.5 + web_search)

- Enrichment: ~$0.05/person fresh, free cached
- Rubric: ~$0.01/event fresh, free cached
- Rationale: ~$0.001/pair fresh, free cached

A 50-person event runs end-to-end for ~$3 the first time, ~$0 thereafter.

## License

TBD.
