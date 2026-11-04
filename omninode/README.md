# Feed OmniNode

The code behind the OmniNode feed maintenance runs described at https://teleionlabs.com/omninode.txt. One Muse model labels new items, and the other audits them. A small tuner adjusts the routing.

```bash
pip install --target .deps numpy
ERANOS_WORKER=/path/to/eranos-checkout ./run_tests.sh
```

`ERANOS_WORKER` needs a `.venv` with Eranos installed. The tests write a small word list of their own. For a real run, set `BANNED_WORDS_FILE` to your word list.

## Limits

- `src/` is the warm-graph and grid library the node runs on.
- It needs a Teleion Fabric address, Meta API keys and an Eranos checkout for its Python environment.
- Files in `deploy/` are samples. Set the paths and key ids for your own machine.
- Spend caps come from the shared worker ledger, so a run stops when a cap is reached.
