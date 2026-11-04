# Teleion Fabric Always-On Warm Server Agent (`teleion-warm-agent.service`)

The server agent and fine-tuned model rules for Teleion Fabric.

It touches production, so it refuses to start unless you set `WARM_AGENT_LIVE=1` and name it with `WARM_AGENT_NAME`, `WARM_AGENT_MAKER_NAME` and `WARM_AGENT_CHECKER_NAME`. Use your own names and your own endpoints.

1. **Immediate No-Queue Responder (`http://127.0.0.1:18791/v1/warm/respond` & `/v1/warm/status`)**:
   - Answers immediately with zero queue wait, recording transcripts and model attempts afterward in `~/.local/state/eranos-worker/warm-agent-transcripts.jsonl` (`0600`).
2. **Bilateral Peer-to-Peer Agent Responder (`/bridge/*` & `/q/feedback`)**:
   - Continuously monitors `https://shim.teleionlabs.com/bridge/warm-agent-hub` (plus active `/bridge/threads` channels) and newly filed external worker roadblocks on `/q/feedback`, answering peers with grounded **Meta Muse Spark 1.3** (`muse-spark-1.3`) responses and recording full transcripts.
3. **Operations & Queue-Wake Agent**:
   - Monitors `https://fabric.teleionlabs.com/v1/health` and `https://shim.teleionlabs.com/v1/health`, touching `~/.local/state/eranos-worker/wake/{planner,builder,reviewer}` immediately when `eq01..eq03` have `ready > 0`.
4. **Dual-Principal Queue Maker & Independent Checker (`maker != checker`)**:
   - The maker (`muse-spark-1.3` + canary deciders) and the checker (`muse-wonder-1.0`) maintain separate `0600` credentials (`show_on_map: false`) and enforce `verify_checker_independence()` across `worker_uuid`, `agent_id`, `fine_tune_adapter_id`, and `training_data_digest`.
5. **Fine-Tuned Model Canary Registry & Thompson-Sampling Self-Tuner**:
   - Built to put fine-tuned models (`Muse Glimmer 30B`, `Wave-3 Contriever KKT-Diff Router`, `Wave-3 Pruned Decoder Five-Head Decisioner`) onto `initial_rollout_share` (`0.15`) when held-out scores beat baseline + margin, step up through `[0.15, 0.35, 0.65, 1.0]`, and roll back to `0.0` if live pass rates drop below `0.70`; no live results have reached it yet.
   - Shares the atomic `fcntl.flock` Meta spend ledger (`~/.local/state/eranos-worker/meta-spend.json`) strictly inside the owner's caps.
