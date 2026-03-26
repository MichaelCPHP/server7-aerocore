# Lab Platform — System Design

Master reference for architecture decisions, data flow, and development patterns.
Update this document as the platform evolves.

**Last updated**: 2026-03-18

---

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│                  Lab Platform                     │
│                                                   │
│  launcher.js (:3200)                             │
│  ├── instances/jubilee/  (:3210, frontend :3280) │
│  ├── instances/tgcm/     (:3211)                 │
│  └── instances/...                               │
│                                                   │
│  (server + plugins from genesis/template/)       │
└──────────────────────────────────────────────────┘
```

## Data Flow

```
Source Data (human-edited, git-tracked)
  data/events.csv        ← master event list
  data/clocks.json       ← clock definitions
  data/signatures.json   ← named remainder signatures
       │
       ▼
Engine (engine.py)
  Reads source data, computes all clock positions,
  detects signatures, generates output CSVs
       │
       ▼
Output CSVs (generated, git-tracked)
  output/database.csv    ← full event database with all clocks
  output/cycles.csv      ← sacred number cycle detection
  output/gaps.csv        ← gap analysis between events
  output/convergence.csv ← year convergence scoring
  output/signatures.csv  ← signature cluster analysis
  output/...             ← 20+ analysis tables
       │
       ▼
SQLite Database (output/jubilee.db — built from CSVs)
  events, cycles, gaps, convergence, signatures,
  knowledge_base, events_fts, kb_fts, event_tags
       │
       ├──▶ Lab UI (:3210) — AI chat queries via SQL
       └──▶ Frontend (:3280) — public site queries via API proxy
```

## Key Design Decisions

### Multiple CSVs, not one master table
Each analysis script produces its own CSV. This matches dbt/analytics engineering best practices:
- Semantic boundaries (cycles ≠ gaps ≠ convergence)
- Independent cacheability (re-run only what changed)
- Debuggable intermediate artifacts
- Self-documenting pipeline outputs

### SQLite as query layer, CSVs as source of truth
- CSVs are git-diffable, human-editable, portable
- SQLite is rebuilt from CSVs (reproducible, disposable)
- Frontend and Lab AI query SQLite, never read CSVs directly
- When scale exceeds ~50K rows, add DuckDB in Python for heavy analytics

### Scripts in the lab, queries in the frontend
- Lab scripts CREATE data (Python, full system access)
- Frontend DISPLAYS data (SQL queries via API)
- No scripts/plugins in the frontend — every visualization is a SQL query
- When a new analysis type is added, add a script in the lab, rebuild SQLite, frontend sees it automatically

### Zero dependencies where possible
- Node.js server: zero npm packages (built-in http, fs, path, sqlite)
- Python scripts: stdlib only (csv, json, sqlite3, graphlib)
- Frontend: vanilla HTML/CSS/JS, no framework
- Charts: Observable Plot via CDN (no npm install)
- When a dependency IS needed, prefer: single file, small footprint, well-maintained

## Data Intake

### Folder Structure

All raw incoming data lives under `data/` in the instance, organized by source:

```
data/
  events.csv              ← MASTER dataset (verified, engine-processed)
  clocks.json             ← Clock definitions
  signatures.json         ← Signature definitions
  uploads/                ← User-uploaded raw data
    research/
      events/
        bible/              ← Bible timeline sources (BibleHub, etc.)
        world-history/
          usa/
          israel/
          uk/
          iran-persia/
          rome/
          egypt/
        church-history/
          reformation/
          early-church/
          councils/
        prophecy/
      calendars/
        hebrew/
        gregorian/
        islamic/
        jubilee/
      persons/
        patriarchs/
        kings/
        prophets/
      geography/
        cities/
        nations/
        temples/
  scraped/                ← Scraper pipeline output
    wikipedia/
      YYYY-MM-DD/           ← Date-stamped scrape runs
    bible-api/
      YYYY-MM-DD/
    bible-dictionary/
      YYYY-MM-DD/
    concordance/
      YYYY-MM-DD/
    lexicon/
      YYYY-MM-DD/
```

### Data Flow: Raw → Verified → Master

```
User uploads file          Scraper runs
  ↓                          ↓
data/uploads/...           data/scraped/source/date/
  ↓                          ↓
  └──────────┬───────────────┘
             ↓
  Lab AI analyzes raw data:
  - Reads uploaded/scraped file
  - Cross-references against existing events.csv
  - Verifies dates (Ussher chronology for Jubilee instance)
  - Detects duplicates
  - Validates required fields
  - Presents analysis for user review
             ↓
  User approves → AI appends to data/events.csv
             ↓
  /rebuild → engine + all analysis scripts + SQLite
             ↓
  Frontend auto-refreshes with new data
```

### Adding Events

**Manual** (small additions):
1. Edit `data/events.csv` directly or ask the lab AI
2. Run `/rebuild` in the chat
3. Commit: `/snapshot "added X events"`

**Upload** (bulk from files):
1. Click upload button (⇧) in file pane — files go to `data/uploads/research/...`
2. Tell the AI: "I uploaded data at data/uploads/research/events/bible/file.csv — analyze it"
3. AI reads, validates, cross-references, presents findings
4. User reviews and approves
5. AI appends verified events to `data/events.csv`
6. Run `/rebuild`

**Scraping** (automated pipelines — planned):
1. Scraper script runs: `python3 plugins/import/scrape_wikipedia.py`
2. Output lands in `data/scraped/wikipedia/YYYY-MM-DD/`
3. AI processes scraped data same as uploads
4. Verified events get appended to master dataset

### Scraper Architecture (planned)

Each scraper is a plugin in `plugins/import/`:

```
plugins/import/
  scrape_wikipedia.py      ← Wikipedia biblical events
  scrape_bible_api.py      ← Bible API verse/timeline data
  scrape_concordance.py    ← Strong's concordance data
  scrape_lexicon.py        ← Hebrew/Greek lexicon entries
```

Each scraper:
- Writes raw output to `data/scraped/{source}/{date}/`
- Includes metadata: source URL, scrape timestamp, raw vs parsed
- Does NOT directly modify `events.csv` — always goes through AI validation
- Idempotent — re-running produces the same output
- Date-stamped folders enable diffing between scrape runs

### Scale Planning

| Rows | Query layer | Analytics | Notes |
|------|-------------|-----------|-------|
| < 1K | SQLite | Python csv module | Current state |
| 1K-10K | SQLite | Python csv module | Fine, no changes |
| 10K-50K | SQLite | Consider DuckDB Python | Analytical queries may slow |
| 50K+ | SQLite (frontend) + DuckDB (lab) | DuckDB Python | Split: DuckDB for analysis, SQLite for serving |

## Experimentation & New Analysis

### Creating a new analysis script
1. Branch: `git checkout -b experiment/new-analysis`
2. Write script in `plugins/analysis/new_script.py`
3. Script reads from `output/database.csv` or SQLite
4. Script writes results to `output/new_analysis.csv`
5. Test: run script, inspect output
6. Add to `plugins/analysis/manifest.json`
7. Rebuild SQLite: `python3 scripts/build_db.py`
8. Test in frontend: SQL queries against new table
9. Merge: `git checkout main && git merge experiment/new-analysis`

### Experimenting with "what if" scenarios
- **Git branches**: change parameters, add/remove events, compare outputs
- **SQLite SAVEPOINT**: in-memory experiments in the lab AI
  ```python
  import sqlite3
  src = sqlite3.connect('output/jubilee.db')
  mem = sqlite3.connect(':memory:')
  src.backup(mem)  # instant copy
  mem.execute("SAVEPOINT experiment")
  # ... modify data, run queries ...
  mem.execute("ROLLBACK TO SAVEPOINT experiment")  # undo
  ```
- **Git worktrees**: parallel experiments in separate directories
  ```bash
  git worktree add ../experiment-1 -b experiment/alt-threshold
  ```

### AI-assisted analysis creation
1. **Hypothesis**: Ask the lab AI "is there a pattern in X?"
2. **Exploration**: AI runs SQL queries to test the idea
3. **Prototype**: AI writes a one-off script to analyze
4. **Formalize**: If promising, convert to a permanent plugin
5. **Run on full dataset**: Pipeline rebuilds everything

## Data Versioning

### Git is the version control system
- Source data and output CSVs are git-tracked
- Tags mark milestones: `git tag v1.0-initial-dataset`
- Branches for experiments
- `.gitattributes` CSV word-diff driver for field-level diffs

### Versioning workflow
```bash
# Before major data changes
git tag v1.2-pre-import
git checkout -b import/wikipedia-events

# After import
python3 engine.py all
python3 scripts/build_db.py
git add data/ output/
git commit -m "data: imported 500 events from Wikipedia"

# Compare to baseline
git diff v1.2-pre-import -- output/database.csv
git diff v1.2-pre-import -- output/convergence.csv

# If good, merge. If bad, discard.
git checkout main
git merge import/wikipedia-events  # or: git branch -D import/wikipedia-events
```

### Rollback
```bash
git checkout v1.2-pre-import -- data/events.csv
python3 engine.py all
python3 scripts/build_db.py
```

## Pipeline (planned)

Using Python's built-in `graphlib.TopologicalSorter`:

```
events.csv ──▶ engine.py ──▶ database.csv
                    │
                    ├──▶ cycle_finder.py ──▶ cycles.csv
                    ├──▶ remainder_scan.py ──▶ remainder_clusters.csv
                    ├──▶ convergence.py ──▶ convergence.csv
                    ├──▶ mirror_symmetry.py ──▶ mirror_symmetry.csv
                    ├──▶ ... (all analysis scripts)
                    │
                    └──▶ build_db.py ──▶ jubilee.db
```

One command: `python3 pipeline.py` — runs everything in dependency order, skips steps whose inputs haven't changed.

## Frontend Architecture

ES module component architecture — each page is a separate reusable JS file.

```
instances/<name>/frontend/
  server.js              ← dev server (static files + API proxy)
  CHANGELOG.md           ← frontend version history
  public/
    index.html             — thin shell (nav + app container + module import)
    style.css              — theme via CSS variables
    js/
      router.js            — URL routing with pushState
      api.js               — query(), api(), apiPost() helpers
      helpers.js           — esc(), slug(), yearFmt(), sigBadge(), md()
      components/
        dashboard.js       — stats, signature wheel (canvas), tables
        events.js          — list with search/filter + detail (clocks, cycles, gaps, complements)
        signatures.js      — list + detail (matching events, time gaps)
        knowledge.js       — KB browser + article viewer (markdown)
        activity.js        — research log with clickable event references
        calculator.js      — interactive year calculator (all 5 clocks)
  theme/
    theme.json             — colors, fonts (CSS variables)
```

### URL routing
```
/                        ← dashboard (stats, signature wheel, recent events)
/events                  ← event list (search, filter by signature)
/events/<slug>           ← event detail (5 clocks, cycles, gaps, complements)
/signatures              ← signature list with descriptions
/signatures/<slug>       ← all events with signature + time gaps
/knowledge               ← KB browser by category
/knowledge/<id>          ← article detail (rendered markdown)
/calculator              ← enter any year → clock readings + signature
/activity                ← research activity log
/activity/<id>           ← log entry detail with event references
```

### Frontend queries SQLite via API proxy
Frontend server proxies `/api/*` to the lab backend. All data comes from SQL queries. No scripts run in the frontend. Calculator uses `/api/calculate?year=N`.

## Technology Choices

### Current stack (zero-dependency)
| Component | Technology | Dependencies |
|-----------|-----------|-------------|
| Lab server | Node.js (built-in http, fs, sqlite) | 0 |
| Lab UI | Vanilla HTML/CSS/JS | 0 |
| Frontend server | Node.js (built-in http) | 0 |
| Frontend site | Vanilla HTML/CSS/JS | 0 |
| Engine | Python (csv, json, sqlite3) | 0 |
| Analysis scripts | Python (csv, json) | 0 |
| Database | SQLite (built-in node:sqlite, Python sqlite3) | 0 |
| Version control | Git | 0 |

### Planned additions (when scale demands)
| Component | When | Technology | Size |
|-----------|------|-----------|------|
| Charts | Frontend needs visualizations | Observable Plot (CDN) | 0 npm deps |
| Pipeline runner | Formalize rebuild-all | graphlib.TopologicalSorter | 0 (stdlib) |
| Heavy analytics | 50K+ rows | DuckDB Python | 20 MB pip |
| Import scripts | Bulk data ingestion | plugins/import/*.py | 0 |
| Structured CSV diff | Complex data comparisons | csvdiff (Go binary) | Single binary |

### Explicitly rejected
| Technology | Reason |
|-----------|--------|
| DVC / lakeFS | Overkill — git handles our data size |
| DuckDB WASM | 144 MB — too heavy for browser |
| Vega-Lite | 5.8 MB + 27 deps — Observable Plot is lighter |
| Evidence.dev | Full BI framework — we have a frontend |
| dbt / Dagster / Airflow | Team infrastructure tools — our scripts + graphlib suffice |
| React / Vue / Svelte | Framework overhead — vanilla JS is sufficient |
| Pandas | Not needed — csv module + SQL handle our patterns |

## Global Template Architecture

All instances run from a shared server template. Plugins and skills are global:

```
genesis/template/
  core/server.js       ← THE server (all labs run this)
  core/index.html      ← Lab UI (chat, viewer, file manager)
  plugins/
    core/              ← Infrastructure scripts
      pipeline.py, build_db.py, data-snapshot.sh, export_transcript.py
    analysis/          ← Analysis scripts (15 scripts + manifest.json)
      remainder_scan.py, convergence.py, cycle_finder.py, ...
  skills/catalog.json  ← Global skill definitions (27 entries)
  workflows.json       ← Named workflow recipes for agents
```

### Skills System

Skills are assembled from three sources (later wins on name collision):
1. **Built-in** — 10 core skills (rebuild, status, query, etc.)
2. **Script skills** — auto-generated from `manifest.json` (each `.py` → `/slash-command`)
3. **Catalog skills** — from `catalog.json`, gated by script availability

All skills **enabled by default** (opt-out model). `lab.json` `skills` array uses glob patterns (`"core/*"`, `"analysis/*"`) to filter categories. Empty = all enabled. Individual toggles via `settings.json`.

### Script Resolution

`resolveScript()` checks: instance `scripts/` → global `plugins/core/` → global `plugins/analysis/`. Returns null if not found (auto-gates catalog entries).

### Instance-Local Scripts

Instances can have their own `scripts/` directory for custom scripts. These are resolved first, before global plugins.

### Cross-Instance Data Access

Instances can reference data from other instances using symlinks:

```bash
# TGCM instance reads Jubilee Lab's KB articles
ln -s ../../jubilee/kb/analysis instances/tgcm/data/source-articles
```

This enables pipelines where one instance generates research and another consumes it for content creation.

## Multi-Instance Architecture

### Active Instances

| Instance | Port | Purpose | Skills |
|----------|------|---------|--------|
| Jubilee Lab | :3210 | Biblical chronology research | 10 core + 15 analysis + 4 utility = 33 |
| TGCM | :3211 | Ministry blog content creation | 10 core + 8 content + 4 utility |

### Instance Isolation

Each instance has:
- Its own `lab.json` (identity, role, port, model, custom skills)
- Its own `data/`, `kb/`, `output/`, `scripts/` directories
- Its own session persistence (`kb/sessions/`)
- Shared access to global plugins (`genesis/template/plugins/`)
- Shared core server (`genesis/template/core/server.js`)

Cross-instance data flows via symlinks (not copies), so new research in Jubilee Lab automatically appears in TGCM's source list.
