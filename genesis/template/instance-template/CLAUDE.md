# {{INSTANCE_NAME}}

{{INSTANCE_DESC}}

## Architecture
- This instance is part of the {{PLATFORM_NAME}} platform
- Server runs from a shared global template (`genesis/template/core/server.js`)
- Global plugins: `genesis/template/plugins/` (core/ and analysis/ subdirectories)
- Global skills catalog: `genesis/template/skills/catalog.json`
- Instance-local scripts go in this instance's `scripts/` directory (optional)
- Data in `data/`, output in `output/`, knowledge base in `kb/`

## Skills System
- All skills are available by default (opt-out model — disable via settings toggles)
- Skills are grouped by category: core, analysis, content, utility, genesis, deployment
- Analysis scripts auto-register as slash commands (e.g., `remainder_scan.py` → `/remainder-scan`)
- Use `/help` to see all available skills
- Chain skills for multi-step research — see workflow recipes in the system prompt

## Creating New Scripts
- Create new scripts locally in this instance's `scripts/` directory first
- Test thoroughly before requesting promotion to global
- To make a script available to all labs, ask the user to promote it via Genesis IDE
- Do NOT write directly to the global template directories

## Development Rules
- Use `/snapshot` before data changes
- Use `/rebuild` after modifying source data
- Use `/query` for ad-hoc SQL queries against the database
- Present findings as data, not doctrine — quantify statistical significance
