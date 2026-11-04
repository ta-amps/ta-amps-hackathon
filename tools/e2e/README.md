# End-to-end test

Tests the live public system as a stranger with no credentials.

```bash
BANNED_WORDS_FILE=/path/to/word-list.json python3 e2e.py
```

With no options it runs the read-only stages, `names` and `crawl`.

**The `fabric`, `shim`, `q` and `browser` stages change live data.** They add unfinished Tasks to the shared queue, a public Task Object and a follow-up, so they refuse to run without `--write`. Use them only on a system you own. `--claim-real` also holds real work until each lease ends. The browser stage needs Playwright and Chrome.
