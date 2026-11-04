# Live decider

Picks a route for each decision the server agents make: a fine-tuned Muse Glimmer on an on-demand GPU, Muse Spark, or a plain rule. `modal_decider.py` serves the fine-tune.

```bash
PYTHONPATH=. python -m pytest tests
```

## Limits

- The holdout data and fine-tuned weights are not in this repository. Set `TELEION_NOTES` to where you keep them.
- The GPU route answers only while an on-demand container is up, so it is not real-time.
