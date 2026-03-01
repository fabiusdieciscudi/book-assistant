SHELL := bash
VENV  := .venv

.PHONY: venv-init

venv-init:
	python -m venv $(VENV)

venv-activate:
	bash --rcfile <(echo "source $(VENV)/bin/activate") -i

pip-install:
	pip install -r requirements.txt
