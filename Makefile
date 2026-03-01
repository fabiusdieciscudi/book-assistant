# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

SHELL := bash
VENV  := .venv

.PHONY: venv-init

venv-init:
	python3 -m venv $(VENV)

venv-activate:
	bash --rcfile <(echo "source $(VENV)/bin/activate") -i

pip-install:
	pip install -r requirements.txt
