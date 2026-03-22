# AeroCore Platform — Claude Code Instructions

Multi-instance platform for AeroCore Material Recovery business operations.

## Global Template Architecture
- All instances run from a shared server: `genesis/template/core/server.js`
- Global plugins: `genesis/template/plugins/` (core/ subdirectory)
- Global skills catalog: `genesis/template/skills/catalog.json`
- Workflow recipes: `genesis/template/workflows.json`
- Instance-specific scripts live in `instances/<name>/scripts/` (resolved before global plugins)

## Platform Structure

```
aerocore-lab/
  launcher.js        — Grid UI at :9200 (start/stop/create instances)
  start.command       — Double-click to open launcher
  instances/         — Lab instances (each is self-contained)
    aerocore/          — Main AeroCore business instance
      lab.json           — Instance config (name, role, port, plugins, skills)
      data/              — Business data
      kb/                — Knowledge base + sessions
      output/            — Generated content
      scripts/           — Instance-local scripts
      frontend/          — Public-facing website (port 9280)
      docs/              — Instance documentation
  docs/              — Platform-level documentation
```

## Business Context
AeroCore is a material recovery and purchasing company specializing in:
- Scrap carbide tooling (end mills, inserts, drills)
- High-performance alloys (Inconel, titanium, Hastelloy)
- Tungsten materials (carbide, solids, scrap)
- Tool steel & HSS
- Aerospace components
- Production surplus
