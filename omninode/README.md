# Feed OmniNode

The code behind the OmniNode feed maintenance runs described at https://teleionlabs.com/omninode.txt. One Muse model labels new items, and the other audits them. A small tuner adjusts the routing.

```bash
ERANOS_WORKER=/path/to/eranos-checkout ./run_tests.sh
```

## Limits

- It needs a Teleion Fabric address, Meta API keys and an Eranos checkout for its Python environment.
- Files in `deploy/` are samples. Set the paths and key ids for your own machine.
- Spend caps come from the shared worker ledger, so a run stops when a cap is reached.
