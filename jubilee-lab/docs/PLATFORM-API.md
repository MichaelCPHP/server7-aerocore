# Jubilee Lab API Reference

**Base URL**: `http://localhost:3210`

## Sessions

### `GET /api/sessions`
List all sessions.

**Response**: `{ data: Session[] }`

```json
{
  "id": "uuid",
  "claudeSessionId": "uuid|null",
  "title": "session title",
  "model": "opus|sonnet|haiku",
  "createdAt": "ISO-8601",
  "lastMessageAt": "ISO-8601",
  "messageCount": 3,
  "totalCost": 0.25,
  "projectId": "uuid|null"
}
```

### `POST /api/sessions`
Create a new session.

**Body**: `{ model?: "opus"|"sonnet"|"haiku", projectId?: "uuid" }`

**Response**: `{ data: Session }`

### `PATCH /api/sessions/:id`
Update session fields (model, title).

**Body**: `{ model?: string, title?: string }`

**Response**: `{ data: Session }`

### `DELETE /api/sessions/:id`
Delete a session and its messages.

### `GET /api/sessions/:id/messages`
Get all messages for a session.

**Response**: `{ data: Message[] }`

```json
{
  "role": "user|assistant|system|thinking",
  "content": "message text",
  "timestamp": "ISO-8601",
  "duration": 5200,
  "cost": 0.12,
  "tool": "Bash|Read|Edit|...",
  "toolId": "toolu_..."
}
```

### `POST /api/sessions/:id/chat`
Send a message and stream the response via SSE.

**Body**: `{ message: string, viewerContext?: object }`

**Response**: `text/event-stream` (Server-Sent Events)

**SSE Event Types**:

| Event | Fields | Description |
|-------|--------|-------------|
| `init` | `sessionId`, `model` | Session initialized |
| `thinking` | `content` | Incremental reasoning token(s) |
| `text` | `content` | Incremental response token(s) |
| `tool_start` | `tool`, `id` | Tool invocation started |
| `tool_desc` | `tool`, `id`, `description` | Full tool description (e.g., the bash command) |
| `tool_output` | `id`, `output` | Tool result (up to 4000 chars) |
| `done` | `result`, `duration`, `cost`, `num_turns`, `usage` | Response complete |
| `error` | `message` | Error occurred |
| `close` | — | Stream ended |

### `POST /api/sessions/:id/export`
Export session transcript to `kb/transcripts/`.

**Body**: `{ title: string, tags?: string, summary?: string, topics?: string }`

**Response**: `{ data: { success: true, output: string } }`

### `POST /api/sessions/:id/auto-save`
Auto-save session transcript with AI-generated metadata.

**Response**: `{ data: { success: true, output: string } }`

### `POST /api/sessions/:id/generate-metadata`
Generate metadata (title, tags, summary, topics) from session messages.

**Response**: `{ data: { title, tags, summary, topics } }`

## Files

### `GET /api/files`
List all project files and directories (recursive, excludes `.git`, `node_modules`, `chat`).

**Response**: `{ data: FileEntry[] }`

```json
{ "name": "events.csv", "path": "data/events.csv", "size": 61440 }
{ "name": "scripts", "path": "scripts", "isDir": true }
```

### `GET /api/files/fingerprint`
Get a hash of all file modification times. Used for efficient polling — client only refreshes file list when hash changes.

**Response**: `{ data: number }`

### `GET /api/file?path=<relative-path>`
Read a file's content. Supports CSV (parsed to rows), markdown, JSON, Python, shell scripts, and other text files.

**Response**: `{ data: FileContent }`

CSV: `{ type: "csv", name, path, headers: string[], rows: object[] }`
Text: `{ type: "md"|"json"|"text", name, path, content: string }`

## SQL Database

### `POST /api/sql`
Execute a read-only SQL query against `output/jubilee.db`.

**Body**: `{ query: string }`

**Response**: `{ data: { columns: string[], rows: object[], rowCount: number, elapsed_ms: number } }`

Write operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.) are blocked with `403`.

**Example**:
```json
{ "query": "SELECT name, year_ad, signature FROM events WHERE signature = 'CROSS' ORDER BY year_ad" }
```

### `GET /api/sql/schema`
Get the database schema — all tables with column names, types, and row counts.

**Response**: `{ data: { [tableName]: { columns: [{name, type}], rowCount: number } } }`

## Data

### `GET /api/data/summary`
Get a summary of the dataset (event count, signatures, clocks).

**Response**: `{ data: { eventCount, signatureCount, clockCount, topSignatures } }`

### `GET /api/scripts`
List available analysis scripts from `scripts/manifest.json`.

**Response**: `{ data: Script[] }`

## Projects

### `GET /api/projects`
List all projects.

**Response**: `{ data: Project[] }`

```json
{ "id": "uuid", "name": "project name", "description": "...", "createdAt": "ISO-8601" }
```

### `POST /api/projects`
Create a new project.

**Body**: `{ name: string, description?: string }`

**Response**: `{ data: Project }`
