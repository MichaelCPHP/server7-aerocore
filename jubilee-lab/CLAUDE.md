# Jubilee Platform — Claude Code Instructions

Multi-instance biblical chronology research platform. Each lab instance is a self-contained workspace with its own data, scripts, and AI chat.

## Global Template Architecture
- All instances run from a shared server: `genesis/template/core/server.js`
- Global plugins: `genesis/template/plugins/` (core/ and analysis/ subdirectories)
- Global skills catalog: `genesis/template/skills/catalog.json`
- Workflow recipes: `genesis/template/workflows.json`
- Instance-specific scripts live in `instances/<name>/scripts/` (resolved before global plugins)

## Platform Structure

```
jubilee-lab/
  launcher.js        — Grid UI at :3200 (start/stop/create instances)
  start.command       — Double-click to open launcher
  instances/         — Lab instances (each is self-contained)
    jubilee/           — Biblical chronology research
      lab.json           — Instance config (name, role, port, plugins, skills)
      settings.json      — Runtime settings (skill toggles, enforcements)
      data/              — Source data (events.csv, clocks.json, signatures.json)
      kb/                — Knowledge base + sessions + transcripts
      output/            — Generated CSVs + SQLite database
      scripts/           — Instance-local scripts (optional)
      frontend/          — Public-facing site
      docs/              — Instance documentation
    tgcm/              — The Great Controversy Magazine (blog publishing)
  docs/              — Platform-level documentation
```

## Skills System
- Skills auto-discovered: builtins (10 core) + analysis scripts (15 from manifest) + catalog entries
- All skills enabled by default — instances opt out via settings toggles
- Analysis scripts in `genesis/template/plugins/analysis/` auto-register as `/slash-commands`
- Catalog skills requiring missing scripts are automatically filtered out

## Key Commands

```bash
node launcher.js              # Start platform launcher (:3200)
/rebuild                      # Run full pipeline (in lab chat)
/status                       # Show pipeline status
/query SELECT ...             # Run SQL query
/help                         # List all skills
```

## Development Rules
- Server reads `lab.json` for identity, role, port, plugins, skills
- System prompt is self-describing (dynamically discovers all capabilities at runtime)
- Enforcements are code-level guardrails (toggleable via gear icon)
- New scripts go in instance `scripts/` first, promote to global via Genesis IDE
- See `docs/SYSTEM-DESIGN.md` for architecture details
