# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""Shared pytest fixtures for the tests."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--skip-rendered", action="store_true", default=False,
                     help="Skip the voices already rendered, instead of checking them again with speech-to-text")
