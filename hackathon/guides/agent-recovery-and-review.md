# Typed agent recovery and lightweight review

Suggested implementation pattern, 2026-10-28. This is engineering guidance, not an event rule or a claim that any particular service implements it. Start with [external agent access](external-agent-access.md) for the illustrative connection flow.

## Make work inspectable

Treat artifacts, contracts, context and evidence as typed records. Treat work requests as leased tasks with explicit input records, expected outputs and completion conditions. A conversation can clarify missing information or propose a smaller dependency graph; it must not redefine authentication or silently relax a type contract.

Use a small initial handshake: identify the caller and access mode, discover tools and schemas, inspect available work, then claim one authorized task. The next useful question is often about one missing field, not a new open-ended conversation before every operation.

## Distinguish omission from invalid input

An optional field may have a documented default. A provided value of the wrong type should return an actionable error. Otherwise, a client that mistakenly sends a JSON string can receive a successful result computed from unrelated demo data.

For a hypothetical tool expecting an object:

```json
{"error":{"code":"invalid_tool_arguments","path":"arguments.value","expected":"object","message":"Send an object, not JSON encoded inside a string."}}
```

Keep the same executable schema behind HTTP and MCP. Test explicit strings, arrays, booleans, nulls, missing fields, empty objects, invalid enums and boundary numbers. In JavaScript validators, use own-property checks and safe dictionary construction so inherited object properties cannot become unchecked defaults.

## Use a bounded correction loop

1. Read the actual tool schema and the task's expected outputs.
2. Validate a proposed call locally when practical; send the smallest sufficient request.
3. On error, preserve the field path and request ID. Correct the identified field once; do not repeat an unchanged request.
4. If another attempt fails, ask for missing information, select a documented alternative, or split the task into smaller dependent tasks. Release or park work when the lease cannot be maintained.
5. Check the returned output and receipt before completing the task. Text that describes a call is not evidence that a native tool ran.

Choose explicit retry, depth, child-count, context and spend limits. A model may propose changes within those bounds. The server still validates scope, schema, budget and current lease before applying a mutation.

## Keep review proportionate

Workers should self-check their work and attach reproducible evidence. Deterministic gates should validate types, hashes, leases and required tests. When independent judgment is required, enqueue a separate review task for a capable agent with a distinct identity. Preserve independent review before public admission of untrusted reusable artifacts.

Server-paid LLM review is a rare last resort when ordinary checks and an independent worker cannot resolve the question within the available evidence and budget. Do not automatically add another paid reviewer to every task, tool call or conversation turn. More review layers can add expense without supplying independent evidence.

## Preserve the public audience boundary

A backend's service credential may see private records that a public visitor cannot. A public status route must apply an explicit public projection instead of relaying everything its service credential can read. Filter namespace, visibility, status and cohort, and omit owner/key/account identifiers. Test with real scoped storage fixtures plus the actual route handler; a fixture that upstream authorization could never return proves less.

## Record attempts and limits

For each experiment, save the configuration and source revision, made-up input, actual tool events, expected/observed output, failure reason, usage when measured, and evidence fingerprint. Keep failed attempts. Do not treat a passing HTTP probe as native-harness certification, a checksum as a correctness proof, request-size limits as a request-rate quota, or declared attribution metadata as independent provenance verification.

A short release note should state what failed before, what changed, which checks actually ran, what remains untested, and how to disable or roll back the change. Keep provider secrets in secure runtime bindings and avoid publishing raw transcripts containing credentials or private work.

This kit's 2026-10-28 [`make check`](../Makefile) run passed the public scan, JSON and relative-link checks, tool/script unit tests and index freshness checks. Those checks validate the kit; they do not establish that a particular agent or hosted service implements the suggested protocol above.

## Private work and server exceptions

Use the [worker-first execution policy](worker-first-execution.md) for private worker access, bounded server inference and measurement, and the [work examples](worker-verb-examples.md) for research, production and operations.
