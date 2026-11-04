# teleionlabs.com. Light only (MUST-FOLLOW rule 13). Stdlib Python and Node 22; the browser check needs a running copy.
PYTHON ?= python3
BASE ?= http://127.0.0.1:8799

.PHONY: film-fixture build test range-test words links check light-check

build:
	$(PYTHON) build.py

film-fixture:
	$(PYTHON) tests/make_film_fixture.py

test: film-fixture build
	node --test tests/worker.test.mjs tests/worker_example.test.mjs tests/network.test.mjs tests/network_client.test.mjs

# Real workerd streaming/Content-Length checks using the existing workspace install.
range-test: film-fixture
	node --test tests/media_range.test.mjs tests/network_runtime.test.mjs

words: build
	$(PYTHON) tests/check_words.py

links: build
	$(PYTHON) tests/check_links.py

check: test range-test words links

# Light, layout and axe on every page under both colour schemes, against BASE (wrangler dev or a deploy).
light-check: build
	node tests/check_site.mjs --base $(BASE)
