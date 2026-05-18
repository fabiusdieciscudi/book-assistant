#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from book_assistant import COMMANDS
from .Html2TxtCommand import Html2TxtCommand
COMMANDS.append(Html2TxtCommand())