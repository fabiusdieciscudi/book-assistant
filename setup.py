#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from setuptools import setup, find_packages
from pathlib import Path
import re

version_file = Path("src/book_assistasnt/Version.py")
version = re.search(r'__version__ = ["\']([^"\']+)["\']', version_file.read_text()).group(1)

setup(
    name="book-assistant",
    version=version,
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)