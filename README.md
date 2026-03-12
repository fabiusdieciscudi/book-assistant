# BookAssistant

A command-line toolkit for authors, providing spell checking, typographic validation, and text-to-speech rendering for `.txt` manuscript files.

## Features

- **[`spellcheck`](docs/SPELLCHECK.md)**                — multilingual spell checking with custom dictionary support
- **[`check-guillemets`](docs/CHECK_GUILLEMETS.md)**    — validates punctuation around guillemets (`«»`) according to Italian typographic conventions
- **[`tts`](docs/TTS.md)**                              — converts text to speech with multi-voice, multi-speaker narration support

All commands accept either a single `.txt` file or a folder. When given a folder, all `.txt` files within it (including subdirectories) are processed in alphabetical order.

---

## Installation

**Requirements:** Python 3.11+, Java 17 or later (for spellcheck), macOS or Linux.

```bash
git clone https://github.com/fabiusdieciscudi/book-assistant.git
cd book-assistant
make venv-init venv-activate
make pip-install
```

The `spellcheck` command requires the `JAVA17_HOME` environment variable to point to a Java 17 or newer installation. 
This is because it uses [LanguageTool](https://languagetool.org/), whose engine is written in Java.

```bash
export JAVA17_HOME=/path/to/java17
```

## Usage

Use the provided wrapper script, which activates the virtual environment automatically:

```bash
./BookAssistant <command> <path> [options]
```

For convenience, you can symlink it somewhere on your `$PATH`:

```bash
ln -s "$(pwd)/BookAssistant" ~/.local/bin/BookAssistant
```

Then call it from anywhere:

```bash
BookAssistant spellcheck my_novel/
BookAssistant check-guillemets chapter01.txt
BookAssistant tts chapter01.txt --output chapter01.wav
```

Do not move the script: it detects the Python file position by looking at its own directory.

### Global options

| Option | Description |
|---|---|
| `--debug` | Enable verbose logging. |
| `--version` | Print version number.   |
| `--dry-run` | Validate input without performing time-expensive operations. |

---

## Commands

### `spellcheck`

Checks spelling across multilingual manuscripts. Language can be switched mid-file using `@language` tags. Supports custom dictionaries for proper nouns and domain-specific terms.

```bash
BookAssistant spellcheck <path> [--dict <dictionary.txt>]
```

→ See [SPELLCHECK.md](docs/SPELLCHECK.md) for full documentation.

---

### `check-guillemets`

Flags suspicious punctuation placement around closing guillemets (`»`).

```bash
BookAssistant  check-guillemets <path>
```

→ See [CHECK_GUILLEMETS.md](docs/CHECK_GUILLEMETS.md) for full documentation.

---

### `tts`

Renders text to a WAV or MP3 file. Supports speaker tags for multi-character narration, voice instructions, and word-level pronunciation patches.

```bash
BookAssistant  tts <path> --voices-config voices.cfg --output output.wav
```

→ See [TTS.md](docs/TTS.md) for full documentation.

---

## License

MIT — © 2026-present by Fabius Dieciscudi