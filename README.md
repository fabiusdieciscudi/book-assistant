# BookAssistant

A command-line toolkit for authors, providing spell checking for `.txt` manuscript files.

## Features

- **[`spellcheck`](docs/SPELLCHECK.md)**                — multilingual spell checking with custom dictionary support
- **[`echo`](docs/ECHO.md)**                            — flags nearby repetitions of the same word (echoes)
- **[`stats`](docs/STATS.md)**                          — per-chapter statistics: words, sentences, *cartelle*, readability indexes

All commands accept either a single `.txt` file or a folder. When given a folder, all `.txt` files within it (including subdirectories) are processed in alphabetical order.

---

## Installation

**Requirements:** Python 3.11+, Java 17 or later (for spellcheck), macOS or Linux.

```bash
git clone https://github.com/fabiusdieciscudi/book-assistant.git
cd book-assistant
make venv-prepare
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
```

Do not move the script: it detects the Python file position by looking at its own directory.

### Global options

| Option      | Description                                                  |
|-------------|--------------------------------------------------------------|
| `--debug`   | Enable verbose logging.                                      |
| `--version` | Print version number.                                        |
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

### `echo`

Flags *echoes*: the same word repeated within a short distance, a common style issue in narrative prose. Words shorter than four letters and a list of very common Italian words are ignored; words that differ only in their final vowel (e.g. *nuovo*/*nuova*) count as the same word.

```bash
BookAssistant echo <path> [--window 150] [--no-colour] [--print-all-lines]
```

→ See [ECHO.md](docs/ECHO.md) for full documentation.

---

### `stats`

Prints a table of per-chapter statistics: words, sentences, paragraphs, *cartelle* and readability indexes (Gulpease, Coleman-Liau). With a LaTeX `.toc` file, page columns are added too.

```bash
BookAssistant stats <path> [--latex-toc <book.toc>]
```

→ See [STATS.md](docs/STATS.md) for full documentation.

---

## License

MIT — © 2026-present by Fabius Dieciscudi
