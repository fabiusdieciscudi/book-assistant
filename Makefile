# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

PYTEST_ARGS=

.PHONY: test test-voices test-new-voices

test:
	source $(VENV)/bin/activate && pytest -s $(PYTEST_ARGS)

test-voices:
	source $(VENV)/bin/activate && pytest -s test/test_voices.py::test_voice $(PYTEST_ARGS)

test-new-voices:
	source $(VENV)/bin/activate && pytest -s test/test_voices.py::test_voice --skip-rendered $(PYTEST_ARGS)

include Makefile-py
