# Platform API Changelog

All changes to the Lab Platform HTTP API (launcher + core server).

## v5.5 - 2026-03-15

### Added (Platform Launcher — :3200)
- `GET /api/instances` — list all lab instances with status
- `POST /api/instances` — create new instance
- `POST /api/instances/:id/start` — start instance
- `POST /api/instances/:id/stop` — stop instance

### Added (Core Server — per instance)
- `GET /api/lab` — instance config (name, icon, color, plugins)
- `GET /api/settings` — enforcement settings
- `PATCH /api/settings` — toggle enforcements
- `GET /api/skills` — list slash command skills
- `POST /api/sessions/:id/skill` — execute skill (SSE)
- `POST /api/upload` — multipart file upload
- `GET /api/research-log` — read activity log
- `POST /api/research-log` — append log entry
- `GET /api/calculate?year=N` — compute clock positions

### Changed
- `POST /api/sessions/:id/export` — reworked: format param (markdown/json/kb-article)
- Removed: `/api/sessions/:id/auto-save`, `/api/sessions/:id/generate-metadata`

## v4.0 - 2026-03-14

### Added
- `POST /api/sql` — read-only SQL query endpoint (SQLite)
- `GET /api/sql/schema` — database schema with table/column/row info
- `GET /api/files/fingerprint` — lightweight hash for change detection polling
- SSE event `thinking` — streams Claude's reasoning tokens in real-time
- SSE event `tool_start` — immediate notification when Claude invokes a tool
- SSE event `tool_desc` — descriptive label once tool input is fully assembled
- SSE field `usage` on `done` event — input/output/cached token counts
- SSE field `num_turns` on `done` event — number of API turns used

### Changed
- `GET /api/files` — now returns all project files/folders (was hardcoded to data/output/kb)
- `GET /api/file` — now supports `.py`, `.sh`, `.txt`, `.yml`, `.yaml`, `.cfg`, `.ini` files
- `POST /api/sessions` — accepts `projectId` parameter
- SSE `tool_output` — increased from 2000 to 4000 char limit
- SSE streaming uses `stream_event` (content_block_delta) for true token-by-token delivery
- Session titles stored in full (no truncation)

### Fixed
- `POST /api/sessions/:id/auto-save` — passes `--project` flag for project subfolder exports
- `POST /api/sessions/:id/export` — passes `--project` flag for project subfolder exports

## v3.1 - 2026-03-14

### Added
- `GET /api/scripts` — list available analysis scripts from manifest
- `GET /api/projects` — list all projects
- `POST /api/projects` — create a project
- `POST /api/sessions/:id/auto-save` — auto-save transcript with generated metadata
- `POST /api/sessions/:id/generate-metadata` — AI-generated tags, summary, topics
- `GET /api/data/summary` — dataset summary (event count, signatures, clocks)

## v3.0 - 2026-03-14

### Fixed
- System prompt only appended on first message (was re-sent on every resume)

## v2.0 - 2026-03-14

### Added
- `GET /api/sessions` — list sessions
- `POST /api/sessions` — create session
- `PATCH /api/sessions/:id` — update session
- `DELETE /api/sessions/:id` — delete session
- `GET /api/sessions/:id/messages` — get messages
- `POST /api/sessions/:id/chat` — SSE chat streaming
- `POST /api/sessions/:id/export` — export transcript
- `GET /api/files` — list browseable files
- `GET /api/file?path=` — read file content
