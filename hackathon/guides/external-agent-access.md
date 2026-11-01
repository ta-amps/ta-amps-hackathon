# How an external agent connects: anonymous vs keyed

This is an implementation guide, not an event rule. Examples use a hypothetical service at `https://fabric.example.com`; replace it with your service's URL and follow its published contract. The example session, key, and audit routes below are application conventions, not endpoints required by MCP. Reviewed 2026-10-27.

Personal assistants, browser agents, and coding harnesses can all use open deterministic tools. Reserve credentials for capabilities that require them: tracked demo mutations, private state, higher quotas, or privileged work. Label the difference clearly in the UI and tool descriptions.

## Discover the service

Publish `/llms.txt`, a machine-readable agent card, a `/connect` page, and a `/connect.json` access contract. Generate tool names, counts, schemas, and connection examples from the executable registry. Verify each advertised tool against `tools/list` in CI.

For a service offering MCP over HTTP, initialize before calling tools:

```bash
export AGENT_BASE_URL=https://fabric.example.com
curl --fail-with-body "$AGENT_BASE_URL/mcp" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"example-agent","version":"1.0"}}}'
```

Use the negotiated protocol version on subsequent requests. Send the initialized notification and follow any session-header requirements in the response. MCP's HTTP transport and initialization rules are described in the [transport specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) and [lifecycle specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle), checked 2026-10-27.

## Mode A: tracked anonymous work

An illustrative service can expose `POST /v1/session/anonymous` and an equivalent `open_anonymous_session` MCP tool. Return an opaque token, principal ID, assigned namespace, immutable labels, expiry, and quota limits. Anonymous means no pre-existing account; it does not mean untracked.

Save the mint response to a private temporary file so a full credential does not land in a shared terminal transcript:

```bash
agent_session_file=$(mktemp)
chmod 600 "$agent_session_file"
curl --fail-with-body "$AGENT_BASE_URL/v1/session/anonymous" \
  -H 'Content-Type: application/json' \
  --data '{"agent_label":"example-assistant"}' > "$agent_session_file"
AGENT_TOKEN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session_token"])' "$agent_session_file")
AGENT_NAMESPACE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["namespace"])' "$agent_session_file")
export AGENT_TOKEN AGENT_NAMESPACE
rm -f "$agent_session_file"
```

Keep the returned namespace, labels, expiry, and limits in the agent's private session state. Use made-up fixtures only. A demo principal must not be able to change its labels, escape its namespace, read another principal's private objects, or create administrative keys. Enforce quota limits on both actions and session issuance so opening more sessions cannot trivially bypass the limits.

## Mode B: scoped API keys

Keep administrator-assisted issuance as a simple option. If you offer self-service keys, authenticate an account first and constrain its permitted scopes. Explain the actual supported flow; do not label an operator-only mint endpoint as public registration.

For this example, a previously issued key uses the same bearer header:

```bash
read -rsp 'API key: ' AGENT_TOKEN
export AGENT_TOKEN
curl --fail-with-body "$AGENT_BASE_URL/mcp" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

Use the same request after anonymous minting. Initialize the connection using the same credential if the server requires authenticated initialization. Do not enable shell tracing while working with credentials.

An illustrative MCP client configuration follows. Client configuration formats vary; use your client's supported secret-reference mechanism rather than committing a literal credential:

```json
{
  "mcpServers": {
    "your-fabric": {
      "type": "http",
      "url": "https://fabric.example.com/mcp",
      "headers": { "Authorization": "Bearer <SESSION_OR_API_KEY>" }
    }
  }
}
```

Store only a one-way token verifier server-side. Display a key identifier or short prefix in management UIs, return the full secret only when minted, and provide owner-scoped listing, revocation, rotation, and expiry. Never embed privileged keys in HTML, JavaScript bundles, URLs, or public repositories.

## Run and verify the noun/verb loop

Discover exact tool schemas before constructing requests. A typical flow is search nouns, find an allowed ready verb, claim it, heartbeat while working, write an artifact with compare-and-set, and submit the result for a receipt. Include the assigned namespace and the current fencing token on every applicable operation. Release or cancel unfinished work according to the service's lease contract.

Use a common audit envelope for anonymous, keyed, and service-binding calls: request ID, timestamp, principal kind, principal identifier, action, resource type and identifier, status, receipt reference, and immutable labels. Give each principal an own-events view; restrict full audit access to operators. Public activity views should show only allowlisted fields and omit private identifiers and content.

Test the full loop with zero initial secrets and again with a scoped API key. Also test cross-principal reads and writes, non-demo claims by demo principals, stale leases, double-claim races, quota responses with `Retry-After`, revocation, and guessed resource identifiers. A successful HTTP status or a receipt hash alone does not prove authorization or concurrency safety.

Browser clients need an explicit CORS policy as well as authorization. For non-cookie public discovery and demo endpoints, permit the required bearer and JSON headers, handle OPTIONS, and expose retry/request identifiers. CORS is a browser transport policy, not permission to read private records. See the [Cloudflare CORS example](https://developers.cloudflare.com/workers/examples/cors-header-proxy/), checked 2026-10-27.
