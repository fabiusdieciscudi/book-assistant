# BookAssistant

A command-line toolkit for authors, providing spell checking, typographic validation, text-to-speech rendering, and illustration cleanup for `.txt` manuscript files and their accompanying `.png` artwork.

## Features

- **[`spellcheck`](docs/SPELLCHECK.md)**                — multilingual spell checking with custom dictionary support
- **[`echo`](docs/ECHO.md)**                            — flags nearby repetitions of the same word (echoes)
- **[`stats`](docs/STATS.md)**                          — per-chapter statistics: words, sentences, *cartelle*, readability indexes
- **[`tts`](docs/TTS.md)**                              — converts text to speech with multi-voice, multi-speaker narration support
- **[`check-guillemets`](docs/CHECK_GUILLEMETS.md)**    — validates punctuation around guillemets (`«»`) according to Italian typographic conventions
- **[`html2txt`](docs/HTML2TXT.md)**                    — converts XHTML chapters (e.g. from TeX4ht) to plain `.txt`
- **[`fix-transparency`](docs/FIX_TRANSPARENCY.md)**    — removes grey-halo artefacts from PNG illustrations caused by near-transparent alpha residue
- **[`publish-wp`](docs/PUBLISH_WP.md)**                — publishes HTML chapters to existing WordPress pages

All commands accept either a single file or a folder. Most of them operate on `.txt` files; the exceptions are `fix-transparency`, which operates on `.png` files, and `html2txt` and `publish-wp`, which operate on `.html` files. When given a folder, all matching files within it (including subdirectories) are processed in alphabetical order.

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

The `tts` command renders voices locally. Models are downloaded from HuggingFace on first use and cached locally (several GB for the neural voices); later runs work offline. On Apple Silicon Macs, Qwen3 and Voxtral voices run on MLX; on other platforms Qwen3 uses PyTorch and Voxtral is not available. The `MacOS:*` voices use the system `say` command and require macOS.

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
BookAssistant tts chapter01.txt --output chapter01.wav
BookAssistant check-guillemets chapter01.txt
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

### `tts`

Renders text to a WAV or MP3 file. Supports speaker tags for multi-character narration, voice instructions, and word-level pronunciation patches.

```bash
BookAssistant tts <path> --voices-config voices.cfg --output output.wav
```

→ See [TTS.md](docs/TTS.md) for full documentation.

---

### `check-guillemets`

Flags suspicious punctuation placement around closing guillemets (`»`).

```bash
BookAssistant check-guillemets <path>
```

→ See [CHECK_GUILLEMETS.md](docs/CHECK_GUILLEMETS.md) for full documentation.

---

### `html2txt`

Converts XHTML files (for instance chapters produced by TeX4ht/make4ht from LaTeX sources) to plain text, one paragraph per line.

```bash
BookAssistant html2txt <path> [--output <file-or-folder>]
```

→ See [HTML2TXT.md](docs/HTML2TXT.md) for full documentation.

---

### `fix-transparency`

Removes grey-halo artefacts from PNG illustrations caused by near-transparent alpha residue (a common side effect of exporting fine-line artwork from some image editors).

```bash
BookAssistant fix-transparency <path> [--threshold 30] [--output fixed.png]
```

→ See [FIX_TRANSPARENCY.md](docs/FIX_TRANSPARENCY.md) for full documentation.

---

### `publish-wp`

Publishes HTML chapters (as produced by TeX4ht) to **existing** WordPress pages through the REST API, updating only the pages whose local file is newer.

```bash
BookAssistant publish-wp <path> --wp-url 'https://example.com/book/c{n}' [--slug-pattern 'ch(\d+)']
```

→ See [PUBLISH_WP.md](docs/PUBLISH_WP.md) for full documentation.

---

## License

MIT — © 2026-present by Fabius Dieciscudi
