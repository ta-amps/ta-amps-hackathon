# Cloudflare & Self-Hosted Deployment Templates

Copyable configuration examples for running any slice of `ta-amps` on your own Cloudflare account (`Workers` + `Durable Objects` + `D1` + `Pages`) or via `docker compose up` at the repository root.

## Files
- [`wrangler.tessera.toml.example`](wrangler.tessera.toml.example): Durable Object SQLite configuration for **Teleion Fabric** (leased tasks (things to do), CAS task objects, and `/mcp`).
- [`wrangler.herma.toml.example`](wrangler.herma.toml.example): Cloudflare Worker + D1 configuration for **The Teleion Fabric shim** (provision search and context shimming).
- [`wrangler.surface.toml.example`](wrangler.surface.toml.example): Stateless surface configuration using `SURFACE_ID` and scoped `TESSERA_SURFACE_TOKEN` secrets.
- [`deploy-cloudflare-stack.sh`](deploy-cloudflare-stack.sh): Dry-runnable deployment script (`DRY_RUN=1 ./deploy-cloudflare-stack.sh`).

See the full walkthrough in [`../../docs/deployment-guide.md`](../../docs/deployment-guide.md).
