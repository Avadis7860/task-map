# task-map

> A **deterministic engine over a graph of missions.** It reads task files where they already live, ranks
> what is actually ready to be worked on, and links each mission to the anchors that justify it — the
> **STAMP** protocol: which north-star axis it serves, which epic it serves or unblocks, which blueprint it
> applies.

**Status: pre-1.0** — the engine is complete and the CLI surface is frozen; the output envelope is a
versioned inter-repo contract (see [`docs/schema-contract.md`](./docs/schema-contract.md)).

A flat list of task files sorted by modification time tells you what changed, not what to do next. task-map
answers the second question: it resolves the dependency DAG, propagates priority through it (a low-priority
task that unblocks an urgent one rises), separates *ready* from *blocked*, and reports the links that have
gone dead.

The sixth tool in the `-map` family (`code-map` · `docs-map` · `front-map` · `bundle-map` ·
`forgemaster-catalogs`). A **standalone CLI**: no service, no network, no daemon, and no mandatory
dependency — it reads your task files live and prints stable JSON.

## What this is *not*

- **Not a task tracker, and not a UI.** It has no store of its own and no web surface. Your tasks stay
  markdown files in your repository; this reads them.
- **Not a build step.** There is no derived index and no cache to refresh — the task corpus is tiny, so it
  is read **live** on every call. No `build`, no `--out`, no index-missing guard.
- **It never touches git.** Writes (`link` / `unlink`) put the file on disk and stop there. The dirty,
  uncommitted file is the hand-off; a human — or an orchestrator — commits it.
- **Not project-specific.** Anything that varies between repositories is declared in
  [`.taskmap.toml`](./.taskmap.toml) (generic defaults if it is absent). No hard-coded path, no assumed
  vocabulary.
- **Not a network client.** Resolving a blueprint reference through an MCP server is an **optional
  integration that degrades honestly** — unreachable means it says so, never that it invents an answer.

## Verbs

| Verb | What it does |
|---|---|
| `taskmap context <slug>` | the STAMP links of one task: axis + epic served/unblocked + blueprint |
| `taskmap rollup axis <name>` | aggregates every mission under one north-star axis |
| `taskmap link <slug> <anchor…>` | sets a STAMP slot (atomic write, never a commit) |
| `taskmap unlink <slug> <anchor…>` | removes a STAMP slot |
| `taskmap doctor` | link coherence: dead blueprint, unknown epic, unresolved axis |
| `taskmap --schema-version` | output-contract version, for consumer negotiation |

`taskmap doctor --root <path>` checks 670 tasks on the reference corpus without a hitch.

## Install

```bash
pip install -e .            # stdlib-pure core, zero dependencies
pip install -e '.[dev]'     # + pytest / ruff / mypy
```

Root resolution is generic: `--root <path>`, else `$TASKMAP_ROOT`, else walk up from the current directory
to the nearest marker (`.taskmap.toml` or `.git/`).

## Design notes

- **Stdlib-pure core** — installable anywhere, offline, with nothing to compile.
- **Frozen output envelope** (`{ok, schema_version}`, exit 0 for reads): an inter-repo contract, see
  [`docs/schema-contract.md`](./docs/schema-contract.md).
- **Live read, no derived index** — the corpus is small enough that a build step would only add a way to be
  stale.
- **No silent cap** — a truncated result says it was truncated.

Architecture, the STAMP protocol and the deliberate boundaries:
[`docs/architecture.md`](./docs/architecture.md).

## License

**Apache-2.0** — see [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).

Installing, running, modifying and redistributing are all granted, commercial use included. §6 grants no
right to the **name**; the patent clause (§3) grants the patents you need and terminates automatically
against anyone who sues the project for infringement.
