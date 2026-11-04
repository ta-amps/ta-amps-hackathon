PYTHON ?= python3
# This kit is the hackathon/ folder of ta-amps/teleionlabs-teleion-fabric, so links in llms.txt and llms-full.txt point there.
INDEX_BASE_URL ?= https://github.com/ta-amps/teleionlabs-teleion-fabric/blob/main/hackathon

.PHONY: check public docs test architecture help index index-check

help:
	@echo "make check   leak and secret scan, JSON and link checks, tool and script tests, index freshness"
	@echo "make index   rebuild INDEX.md, KEYWORDS.md, llms.txt and llms-full.txt"

check: public docs test architecture index-check

public:
	$(PYTHON) scripts/check_public.py .

docs:
	$(PYTHON) scripts/check_docs.py .

test:
	$(PYTHON) -m unittest discover -s tools/transcribe -p 'test_*.py'
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'

architecture:
	$(PYTHON) scripts/check_architecture.py .

index:
	INDEX_BASE_URL=$(INDEX_BASE_URL) $(PYTHON) scripts/build_index.py

index-check:
	INDEX_BASE_URL=$(INDEX_BASE_URL) $(PYTHON) scripts/build_index.py --check
