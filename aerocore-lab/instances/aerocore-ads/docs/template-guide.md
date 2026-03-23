# Ads Instance Template Guide

This instance is designed as a reusable template for paid advertising across different businesses in the server ecosystem.

## Cloning for a New Business

### Step 1: Copy the instance
```bash
cp -r instances/aerocore-ads instances/{new-business}-ads
```

### Step 2: Update lab.json
Change these fields:
- `name` — New business name + " Ads"
- `description` — Business-specific ad description
- `port` — Next available port (check launcher)
- `color` — Pick a unique color for the grid
- `role` — Replace all AeroCore business context with new business details

### Step 3: Update CLAUDE.md
Replace the "Business Context" section with the new business's:
- Products/services being advertised
- Target audiences and industries
- Key value propositions
- Website URL/port

Keep these sections unchanged:
- Ad Platform Integration (MCP servers, APIs)
- Safety Rules
- UTM Parameter Standard
- Directory Structure

### Step 4: Update docs/
- `google-ads-setup.md` — Update keyword categories, campaign strategy, negative keywords
- `meta-ads-setup.md` — Update audiences, ad copy, creative guidelines

### Step 5: Configure credentials
Each business instance needs its own:
- Google Ads account + API credentials
- Meta Business Manager + access tokens
- Separate Pixel IDs and conversion actions

## MCP Server Architecture

MCP servers are installed at the **server root level**, not per-instance:

```
SERVER7-AEROCORE/
  mcps/                        <-- All MCP servers for this server
    registry.json              <-- Index of installed MCPs
    google-ads-mcp/            <-- Google Ads (promobase, full R/W)
    meta-ads-mcp/              <-- Meta Ads (pipeboard, 30+ tools)
    ads-unified-mcp/           <-- Adspirer unified (cloud-hosted)
```

- **registry.json** lists all installed MCPs with their paths, commands, and required env vars
- Each instance's `lab.json` references MCPs by registry key and `mcpRegistryPath`
- MCP servers are shared across instances on the same server
- Each instance has its own credentials (different ad accounts per business)

When cloning to a different server:
1. The `mcps/` directory can be copied or re-cloned on the target server
2. Run dependency install (`uv sync` or `uv venv && uv pip install -r requirements.txt`)
3. Update paths in the instance `lab.json` if the server root differs
4. Configure new credentials for the new server's ad accounts

## Port Allocation
The launcher auto-assigns ports starting at 9211. When creating manually:
- Check existing ports in all `lab.json` files
- Backend port: next available (9211, 9212, etc.)
- Frontend port: backend + 70 (9281, 9282, etc.)

## Instance Independence
Each ads instance is fully self-contained:
- Own session history in `kb/`
- Own campaign data in `data/`
- Own generated reports in `output/`
- Own automation scripts in `scripts/`
- Shared global plugins from `genesis/template/plugins/`
