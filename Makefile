# Checks for the whole repo. The hackathon guide keeps its own Makefile in hackathon/.
PYTHON ?= python3

.PHONY: help check public guide index

help:
	@echo "make check   private-name and secret scan of the whole repo, then the hackathon guide's own checks"
	@echo "make index   rebuild the hackathon guide's INDEX.md, KEYWORDS.md, llms.txt and llms-full.txt"

check: public guide

public:
	$(PYTHON) hackathon/scripts/check_public.py .

guide:
	$(MAKE) -C hackathon check PYTHON="$(PYTHON)"

index:
	$(MAKE) -C hackathon index PYTHON="$(PYTHON)"
