# Live decider

Picks a route for each decision the server agents make: a fine-tuned Muse Glimmer on an on-demand GPU, Muse Spark, or a plain rule. `modal_decider.py` serves the fine-tune.

```bash
PYTHONPATH=. python -m pytest tests
```

`--publish` writes a public record. It refuses to run until you set `DECIDER_RECORD_KEY` to your own key.

## Limits

- The holdout data and fine-tuned weights are not in this repository. Set `DECIDER_HOLDOUT`, `DECIDER_MODAL_PYTHON` and `DECIDER_MODAL_CLI` for your own copies.
- The GPU route answers only while an on-demand container is up, so it is not real-time.
