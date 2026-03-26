# Platform Changelog

All changes to the Lab Platform core, launcher, and shared infrastructure.

## [v6.0] - 2026-03-18

### Added
- **Global Source of Truth** — platform now runs from `genesis/template/core/server.js`
  - Local `core/` and `plugins/` directories removed
  - All plugins and skills served from global template
  - Instance-local scripts in `scripts/` still take priority via `resolveScript()`
- **Dynamic Skills System** — analysis scripts auto-register as slash commands
  - 15 analysis scripts → `/remainder-scan`, `/convergence`, `/frequency`, etc.
  - All skills enabled by default (opt-out model)
  - Skill toggles persist via `settings.json`
  - Info tooltips with category, description, usage, input/output, chains
  - Skills grouped by category (core, analysis, content, utility)
- **Workflow Recipes** — named patterns in `genesis/template/workflows.json`
  - Deep Analysis, Pattern Discovery, Data Import, Date Investigation, etc.
  - Injected into agent system prompt with trigger conditions
- **Enhanced Agent Guidance** — system prompt now includes:
  - Skills grouped by category with chain metadata
  - Workflow recipes with when-to-use guidance
  - Category descriptions
- **CLAUDE.md** created for Jubilee instance (was missing)
- **Documentation overhaul** — SKILLS.md, SCRIPTS.md, SYSTEM-DESIGN.md updated

### Changed
- Skills now come from 3 sources: builtins + auto-generated scripts + catalog
- Catalog skills gated by script availability (content skills only in TGCM)
- All docs updated to reference global template paths instead of local

### Removed
- Local `core/` directory (server.js comes from global template)
- Local `plugins/` directory (plugins come from global template)
- Empty `scripts/` in jubilee/frontend/

## [v5.6] - 2026-03-16

### Added
- **Instance-specific skills** — `lab.json` can define custom slash commands via `skills` array
  - Server loads instance skills alongside built-in platform skills
  - Scripts resolved via `resolveScript()` (instance scripts/ first, then plugins/)
  - Shows in `/help` and system prompt automatically
- **TGCM instance** — "The Great Commission Ministries" content creation lab
  - Transforms Jubilee Lab research articles into ministry blog posts
  - 7 custom skills: /sources, /drafts, /draft, /categorize, /set-status, /publish, /taxonomy
  - Nested hashtag taxonomy (6 domains, 80+ leaf categories)
  - Draft lifecycle: raw → draft → refined → review → published
  - Cross-instance symlink to Jubilee Lab KB articles (data/source-articles/)
  - `scripts/draft_manager.py` — draft CRUD, categorization, taxonomy display
  - Full docs: INSTANCE-DESIGN.md, SKILLS.md, SCRIPTS.md

### Changed
- `core/server.js` `getSkills()` now merges built-in skills with `LAB.skills` from lab.json
- Updated SYSTEM-DESIGN.md with instance-specific skills and multi-instance architecture sections

## [v5.5] - 2026-03-15

### Added
- **Lab Platform** — multi-instance launcher at :3200 with grid UI
  - Start/stop/create instances, auto-opens browser
  - Create New Lab modal with icon picker, auto-port assignment
- **Configurable core** — `core/server.js` reads `lab.json` from any instance
  - Self-describing system prompt (9 dynamic sources)
  - UI adapts branding via `/api/lab`
- **Plugin system** — `plugins/core/` (shared), `plugins/analysis/` (domain-specific)
- **Pipeline runner** — 16-step DAG with mtime caching (`plugins/core/pipeline.py`)
- **9 slash command skills** — /rebuild, /status, /query, /analyze, /help, /db-stats, /snapshot, /uploads, /log
- **Enforcement system** — auto-snapshot, schema validation, circuit breaker, duplicate detection, audit trail
  - Settings UI (gear icon), toggleable at runtime
  - Claude Code PreToolUse hooks for platform-level enforcement
- **File upload** — `POST /api/upload`, `data/uploads/` organized by research category
- **Research activity log** — `kb/research-log.json`, `/api/research-log`, `/log` skill
- **Year calculator** — `GET /api/calculate?year=N`
- **Auto-logging** — /rebuild and /analyze auto-append to research log

### Changed
- Session persistence: tool outputs now saved (full history on reload)
- Export reworked: 3 formats (Markdown, JSON, KB Article) with session ID
- Removed auto-save timer and transcript system (sessions+messages are source of truth)
- All analysis scripts use `LAB_INSTANCE` env var for path resolution
- Stale pre-platform files removed from root directory

## [v4.0] - 2026-03-14

### Added
- **SQLite database layer** (`output/jubilee.db`) — all CSVs + KB indexed with FTS5 full-text search
- `scripts/build_db.py` — builds database from flat files, supports `--stats` and `--query "SQL"`
- `POST /api/sql` — read-only SQL query endpoint for Claude (write operations blocked)
- `GET /api/sql/schema` — returns full database schema with row counts
- System prompt includes full database schema so Claude can query all tables directly
- Benchmark suite: `benchmark_db.py` (A/B config tests), `benchmark_realworld.py` (15 API query patterns)
- All 15 benchmark queries execute in < 1ms; SQL is 5.5x faster than CSV reads
- **Real-time streaming** — reasoning, tool calls, and output stream token-by-token
  - Thinking blocks stream live with spinning gear, persist as permanent messages
  - Tool calls show immediately with descriptive labels (bash command, file path, search pattern)
  - Tool output renders inline, scrollable for long results
  - Uses Claude CLI `stream_event` (content_block_delta) for true incremental streaming
- **Session/project state in knowledge base** (`kb/sessions/`) — survives reboots, part of the project
- Sessions restored from existing transcripts on migration
- Restored `start.command` — double-click web app launcher (no tmux)

### Changed
- **Retired tmux workstation** — web app is the only interface
  - Removed `start.command` (tmux 5-pane launcher)
  - Removed `scripts/browse-kb.sh`, `browse-scripts.sh`, `browse-sheets.sh` (fzf browsers)
  - Removed `index.html` (root) — old standalone data viewer
  - Removed `planning/` — superseded planning docs
- **Dynamic file manager** — shows all files and folders, no hardcoded dirs or extensions
- File pane auto-refreshes every 10s via fingerprint polling
- `CLAUDE.md` rewritten for web-app-only architecture
- `chat/start.sh` only regenerates CSVs when source data files are newer than `database.csv`
- Session titles stored in full (no ellipsis truncation) — sidebar handles visual truncation via CSS
- Tool output always visible inline (no disappearing collapsible blocks)
- Bash tool icon changed from triangle to chevron (no longer looks like an expand button)
- Reasoning blocks render inline like tool calls — always visible, scrollable

### Fixed
- Sessions assigned to active project when created
- Transcript exports save to project subfolders: `kb/transcripts/<project-name>/`
- Auto-save refreshes file browser on completion
- File tree renders subdirectories correctly
- State moved from `/tmp/` (purged by macOS) to persistent project storage

## [v3.1] - 2026-03-14

### Added
- Collapsible sidebar with hamburger toggle
- Projects system — create named project categories, sessions tagged to projects
- Auto-save transcripts (30s debounce after assistant response)
- AI-generated export metadata (tags, summary, topics extracted from conversation)
- Scripts manifest (`scripts/manifest.json`) — 15 analysis modules with chain suggestions injected into system prompt
- Data versioning — `.gitattributes` CSV word-diff driver, `scripts/data-snapshot.sh` for tagged commits

### Changed
- Export modal auto-populates metadata via `/api/sessions/:id/generate-metadata`
- System prompt now includes available scripts with chaining suggestions
- Sidebar footer shows Scripts and Projects navigation links

## [v3.0] - 2026-03-14

### Fixed
- System prompt only sent on first message (was re-sent on every resume, bloating context/cost)
- CSV row index tracking preserved through sort/filter (`_origIndex`)
- Search debounce (300ms) prevents UI lag on large datasets
- Row cache with key invalidation prevents stale data display
- All silent `catch {}` blocks replaced with logged errors

## [v2.0] - 2026-03-14

### Added
- AI chat system — Claude Code CLI proxy with SSE streaming
- Session management — create, resume, delete, rename sessions
- Multi-model support — opus, sonnet, haiku via model selector
- Data viewer with CSV table, markdown renderer, JSON viewer
- Context bridge — viewer selection state injected into Claude prompts
- Data enrichment — automatic remainder/signature/event context lookup
- File browser with data/, output/, kb/ sections
- Export transcripts to `kb/transcripts/` with metadata and CSV index
- Tab system for multiple open files

## [v1.0] - 2026-03-13

### Added
- Initial project: Jubilee Engine with biblical chronology data
- `engine.py` — core calculation engine (events, clocks, signatures, gaps, cycles)
- `data/events.csv` — 171 events spanning 4004 BC to present
- `data/clocks.json` — 3 clock systems (Cosmic, Israel, Church)
- `data/signatures.json` — named remainder signatures
- 10 analysis scripts: cycle_finder, remainder_scan, convergence, mirror_symmetry, anchor_dates, complement_pairs, frequency, gematria, islamic_overlay, sabbatical_slots
- Knowledge base with articles in kb/analysis/, kb/events/, kb/cycles/, kb/persons/, kb/sources/
- tmux 5-pane workstation with VisiData, fzf browsers, Claude Code CLI
- `start.command` — double-click launcher for macOS
