PY ?= .venv/bin/python
STORYBOARD ?= storyboard.json
SHOT ?=

.PHONY: setup validate test narration narration-shot radio-cut

setup:
	$(PY) -m pip install -r requirements.txt

validate:
	$(PY) -m pipeline.validate $(STORYBOARD)

test:
	$(PY) -m pytest -q

narration:
	$(PY) -m pipeline.narration --all --storyboard $(STORYBOARD)

narration-shot:
	@if [ -z "$(SHOT)" ]; then echo "Set SHOT=S01"; exit 1; fi
	$(PY) -m pipeline.narration --shot $(SHOT) --storyboard $(STORYBOARD)

radio-cut:
	$(PY) -m pipeline.radio_cut --storyboard $(STORYBOARD)
