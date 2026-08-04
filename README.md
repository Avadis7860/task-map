# task-map

> A **deterministic engine over a graph of missions.** It reads task files where they already live, resolves
> the dependency graph between them, and links each mission to the anchors that justify it — the **STAMP**
> protocol: which north-star axis it serves, which epic it serves or unblocks, which blueprint it applies.

**Status: pre-1.0.** Nothing has been released yet. The CLI surface is stable and every response carries a
`schema_version` so a consumer can negotiate; the envelope is documented in
[`docs/schema-contract.md`](./docs/schema-contract.md).

A flat list of task files sorted by modification time tells you what changed, not what to do next. task-map
answers the second question: it resolves the dependency DAG, propagates priority through it (a low-priority
task that blocks an urgent one rises with it), separates *ready* from *blocked*, and reports the links that
have gone dead.

**Two surfaces, and they differ.** The **CLI** reads and writes the STAMP links of a task, aggregates work
under an axis, and audits the coherence of the graph. The **readiness ranking** — DAG resolution, priority
propagation, ready-vs-blocked — is a **Python API** (`taskmap.classify`, `taskmap.core.graph`) meant to be
called by an orchestrator. It has no verb of its own today.
[`forgemaster`](https://github.com/Avadis7860/forgemaster) is one such caller, and the reason that API
exists; it is not required to use this tool.

A **standalone tool**: no service, no daemon, no network, and no runtime dependency. It reads your task
files live and prints stable JSON.

## What this is *not*

- **Not a task tracker, and not a UI.** It has no store of its own and no web surface. Your tasks stay
  markdown files in your repository; this reads them.
- **Not a build step.** There is no derived index and no cache to refresh — the corpus is small enough that
  a build step would only add a way to be stale. No `build`, no `--out`, no index-missing guard.
- **It never touches git.** Writes (`link` / `unlink`) put the file on disk and stop there. The dirty,
  uncommitted file is the hand-off; a human — or an orchestrator — commits it.
- **Not a network client.** It never calls anything. A blueprint reference is *emitted*, not resolved:
  `context` reports `resolved: false` with a reason, and a programmatic consumer may inject its own
  resolver. Ours resolves against an MCP server —
  [`forgemaster-catalogs`](https://github.com/Avadis7860/forgemaster-catalogs) — but that lives entirely on
  the consumer's side. A resolver that finds nothing yields a dead-link report, never an invented answer.
- **Not a generic file crawler.** It reads a specific layout and a specific frontmatter, described below.
  Point it at a repository that does not use them and it will find nothing.

## What it configures, and what it fixes

Two things are yours, declared in [`.taskmap.toml`](./.taskmap.toml):

| Key | What it moves |
|---|---|
| `[tasks] subdir` | where the buckets live under the repository root — **default `.claude/tasks`** |
| `[vocab] priorities` · `services` · `categories` | the business vocabulary. `priorities` is **ordered**: it drives the ranking |

Everything else is fixed by the engine and is not configurable: the bucket names (`backlog`, `active`,
`archive`), the terminal statuses (`done`, `cancelled`), the `ROADMAP-` prefix that marks an epic, and the
frontmatter field names below.

## The task files it reads

```
<root>/<tasks.subdir>/backlog/**/*.md      # default: .claude/tasks/backlog/…
<root>/<tasks.subdir>/active/**/*.md
<root>/<tasks.subdir>/archive/**/*.md
```

`README.md`, `INDEX.md` and `TEMPLATE*.md` are skipped. A file named `ROADMAP-<something>.md` is an
**epic** by convention; task ids quoted `` `like-this` `` in its body are read as its children.

One task is one file, with YAML frontmatter:

```yaml
---
id: my-task              # defaults to the filename
status: backlog          # defaults from the bucket; done|cancelled must live in archive/
priority: P1             # from [vocab] priorities; defaults to P2 whatever the vocabulary
depends_on: [other-task] # the DAG edges
tags: []
epic: ROADMAP-something  # STAMP — the epic this serves
serves: []               # STAMP — north-star axes served
unblocks: []             # STAMP — what it unblocks
blueprint: some-pattern  # STAMP — the pattern applied (emitted, not resolved)
template: []             # STAMP — the step skeletons that pattern points to
---
```

`axis` is never written: it is **derived** from the epic, never stored on the task.

## Verbs

| Verb | What it does |
|---|---|
| `taskmap context <slug>` | the STAMP links of one task: axis + epic served/unblocked + blueprint |
| `taskmap rollup axis <name>` | aggregates every mission under one north-star axis |
| `taskmap link <slug> <anchor…>` | sets a STAMP slot (atomic write, never a commit) |
| `taskmap unlink <slug> <anchor…>` | removes a STAMP slot |
| `taskmap doctor` | link coherence: dangling dependencies, cycles, unknown epic, unresolved axis |
| `taskmap --schema-version` | output-contract version, for consumer negotiation |

`link` and `unlink` accept `--dry-run`: it prints the edit it would make and writes nothing.

Reads exit `0` even when they report a problem — the verdict is in the payload, not in the exit code.

## Install

Requires **Python ≥ 3.11** (the config reader uses `tomllib` from the standard library).

```bash
pip install -e .            # zero runtime dependencies
pip install -e '.[dev]'     # + pytest / ruff / mypy
```

Three names, deliberately: the distribution is `task-map`, the package is `taskmap`, the command is
`taskmap`.

Root resolution is generic: `--root <path>`, else `$TASKMAP_ROOT`, else walk up from the current directory
to the nearest marker (`.taskmap.toml` or `.git/`).

## Design notes

- **Stdlib-pure core** — no runtime dependency, nothing to compile, works offline once installed.
- **Live read, no derived index** — see above; there is nothing to rebuild and nothing to invalidate.
- **Atomic writes** — a write goes through a temporary file and a rename, so a task file is never left
  half-written. It stops at the filesystem: committing is somebody else's job.
- **Stable envelope** — `{ok, schema_version, …}` on every response, so a consumer can branch on the
  version instead of sniffing the shape.

Architecture, the STAMP protocol and the deliberate boundaries:
[`docs/architecture.md`](./docs/architecture.md).

Sibling tools, same posture — deterministic, local, stdlib-first:
[`code-map`](https://github.com/Avadis7860/code-map) ·
[`docs-map`](https://github.com/Avadis7860/docs-map) ·
[`front-map`](https://github.com/Avadis7860/front-map).

The design documentation under `docs/` is written in French; the code, the identifiers and this page are in
English. CLI help and diagnostic messages are currently French too.

## License

**Apache-2.0** — see [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).

Installing, running, modifying and redistributing are all granted, commercial use included. §6 grants no
right to the **name**; the patent clause (§3) grants the patents you need and terminates automatically
against anyone who sues the project for infringement.
