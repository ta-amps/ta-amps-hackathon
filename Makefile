# Checks for the whole repo. The hackathon guide keeps its own Makefile in hackathon/.
PYTHON ?= python3

.PHONY: help check public docs sandbox guide index

help:
	@echo "make check    private-name/secret scan, root doc/JSON check, sandbox tests, and hackathon guide checks"
	@echo "make sandbox  run the offline developer sandbox unit and end-to-end smoke tests"
	@echo "make index    rebuild the hackathon guide's INDEX.md, KEYWORDS.md, llms.txt and llms-full.txt"

check: public docs sandbox guide

public:
	$(PYTHON) hackathon/scripts/check_public.py .

docs:
	$(PYTHON) hackathon/scripts/check_docs.py .

sandbox:
	$(PYTHON) -m unittest discover -s sandbox -p 'test_*.py'
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

guide:
	$(MAKE) -C hackathon check PYTHON="$(PYTHON)"

index:
	$(MAKE) -C hackathon index PYTHON="$(PYTHON)"
