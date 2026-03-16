# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

SHELL := bash
VENV  := .venv
BUILD=build
TEST_RESULTS=$(BUILD)/test-results
DEBUG=--debug

X := /Volumes/Aguieloun/Fabius Dieciscudi/Jacques Messadié/1. Jacques Messadié gioca a sciarada/Latex
Y := target/txt-audio/Jacques_Messadié_gioca_a_sciaradach33.txt

.PHONY: venv-init clean test1 test2 venv-init

all:
	@true

clean:
	-rm -rf $(BUILD)

test1: $(TEST_RESULTS)
	# perl -0777 -ne 'print /(RIFF.*)/s'
	BookAssistant tts $(DEBUG) --voices-config test/multi-voice.conf --instruct-config test/instruct.conf --qwen3-clone-config $(CLONED_VOICES)/qwen3-clones.conf --output $(TEST_RESULTS)/test1.aiff test/test1.txt
	afplay $(TEST_RESULTS)/test1.aiff

test2: $(TEST_RESULTS)
	BookAssistant tts $(DEBUG) --max-lines 20 --voices-config test/multi-voice-2.conf --instruct-config test/instruct.conf --output $(TEST_RESULTS)/test2.aiff '$(X)/$(Y)'

test3: $(TEST_RESULTS)
	# BookAssistant tts $(DEBUG) --max-lines 20 --voices-config test/multi-voice-2.conf --instruct-config test/instruct.conf --word-patches test/word-patches.conf --output $(TEST_RESULTS)/test3.aiff test/test3.txt
	BookAssistant tts $(DEBUG) --max-lines 20 --voices-config test/multi-voice-2.conf --instruct-config test/instruct.conf --word-patches test/word-patches.conf --format mp3 --output $(TEST_RESULTS)/test3.mp3 test/test3.txt
	afplay $(TEST_RESULTS)/test3.mp3

test4: $(TEST_RESULTS)
	BookAssistant tts $(DEBUG) --max-lines 20 --voices-config test/multi-voice-clone.conf --instruct-config test/instruct.conf --word-patches test/word-patches.conf --qwen3-clone-config test/qwen3-clone.conf --output $(TEST_RESULTS)/test4.aiff test/test4.txt
	afplay $(TEST_RESULTS)/test4.aiff

test5: $(TEST_RESULTS)
	BookAssistant tts $(DEBUG) --max-lines 20 --voices-config test/multi-voice-clone.conf --instruct-config test/instruct.conf --word-patches test/word-patches.conf --qwen3-clone-config $(CLONED_VOICES)/qwen3-clones.conf --output $(TEST_RESULTS)/test4.aiff test/test4.txt
	afplay $(TEST_RESULTS)/test4.aiff

$(BUILD):
	mkdir -p $(BUILD)

$(TEST_RESULTS):
	mkdir -p $(TEST_RESULTS)

venv-init:
	python -m venv $(VENV)

venv-activate:
	bash --rcfile <(echo "source $(VENV)/bin/activate") -i

pip-install:
	pip install -r requirements.txt
