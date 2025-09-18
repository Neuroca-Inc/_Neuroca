# Memory Sample Packs

The NeuroCA memory CLI now ships with curated seeding scenarios that developers can import directly into a local environment. Each pack contains a JSON Lines payload that exercises the multi-tier memory lifecycle so you can validate cognitive flows without crafting fixtures from scratch.

## Available Packs

Run the CLI to see the bundled scenarios:

```bash
nca memory sample-packs list
```

Example output:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Slug                      ┃ Title                     ┃ Tags         ┃ Default CLI Args     ┃ Description                                              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ collaborative-brainstorm │ Collaborative Brainstorm │ collaboration│ --user team-alpha    │ Captures a multi-stage product ideation workshop…       │
│ customer-support-playbook│ Customer Support Playbook│ support      │ --user support-pod-a │ Follows an enterprise support incident from intake…     │
└───────────────────────────┴───────────────────────────┴──────────────┴──────────────────────┴────────────────────────────────────────────────────────┘
```

## Exporting a Pack

Use the `export` sub-command to write a pack to disk. Provide either a target file or a directory. The CLI will fail fast if the file already exists unless you pass `--overwrite`.

```bash
nca memory sample-packs export collaborative-brainstorm --output seeds/collab.jsonl
```

The command prints a hint for seeding the exported payload:

```
Hint: nca memory seed seeds/collab.jsonl --user team-alpha --session brainstorm-2024q4
```

## Seeding a Scenario

After exporting, call the standard `seed` command. The recommended `--user` and `--session` values from the hint ensure metadata stays consistent across the bundled memories.

```bash
nca memory seed seeds/collab.jsonl --user team-alpha --session brainstorm-2024q4
```

Once seeded, you can run maintenance cycles or retrieval flows against realistic data without assembling ad-hoc fixtures.

## Directory Layout

Sample packs live in `src/neuroca/memory/seeding/packs/`. They are version controlled alongside the codebase, so updates to the memory manager can ship with refreshed fixture data when scenarios evolve.
