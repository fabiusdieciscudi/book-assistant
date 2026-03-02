# Echo Checker

BookAssistant's `echo` command scans `.txt` files for *echoes*: the same word repeated within a short distance. Echoes are a common style issue in narrative prose, and they are easy to miss when re-reading one's own text.

---

## Basic Usage

```bash
BookAssistant echo <path>
```

`<path>` can be a single `.txt` file or a folder. When a folder is given, all `.txt` files in it (including subdirectories) are processed in alphabetical order. Each file is analysed independently: echoes are never reported across file boundaries.

---

## What It Checks

The text is split into sentences at `.`, `!`, `?` and `…`. A sentence may span several lines. Words are then extracted from each sentence and compared, case-insensitively, with the words that precede them.

### Which words are considered

- Apostrophes (`'` and `’`) separate words, so *l'aereo* yields *aereo*.
- Hyphenated compounds (e.g. *grigio-verde*) count as a single word.
- Words shorter than four letters are ignored.
- A built-in list of very common Italian words is ignored: articulated prepositions (*della*, *nella*, …), demonstratives (*questo*, *quella*, …), frequent adverbs and conjunctions (*sempre*, *quindi*, *però*, …) and common forms of auxiliary and modal verbs (*aveva*, *sarebbe*, *poteva*, …).

### When two words match

Two words are reported as an echo when they are identical, or when they have the same length and differ only in their final letter, provided that both final letters are vowels. This catches gender and number variants such as *nuovo*/*nuova* or *bello*/*belli*.

### How far back it looks

Each word is compared with the previous *N* considered words (ignored words do not count), where *N* is set by `--window` (default: 150).

---

## Output

Each sentence containing at least one echo is printed to stdout, prefixed by the file name and the sentence number (counted from 0 within the file). Line breaks inside a sentence are replaced by spaces.

Repeated words are highlighted:

- in **red** when the same word occurs more than once in the same sentence;
- otherwise in a colour chosen from a fixed palette. The colour depends only on the word (ignoring its final letter), so it stays the same across sentences, files and runs, making it easy to pair the occurrences of an echo.

With `--no-colour`, repeated words are wrapped in braces instead:

```
chapter01.txt[ 12] Il vecchio {aereo} sorvolò la valle, poi l'{aereo} scomparve oltre il crinale.
```

At the end of each file a summary is written to stderr, either `chapter01.txt: Occurrences: 7` or `No nearby word repetitions found.`

---

## Options

| Option              | Description                                                        |
|---------------------|--------------------------------------------------------------------|
| `--window <n>`      | Number of preceding words searched for repetitions (default: 150). |
| `--no-colour`       | Disable colours; repeated words are wrapped in `{braces}` instead. |
| `--print-all-lines` | Also print sentences with no repetitions.                          |
| `--debug`           | Enable verbose logging.                                            |

---

## Notes

- The ignore list is tuned for Italian. Other languages can be checked, but their frequent function words will be reported.
- `@language` tags are not stripped: a tag such as `@english` repeated within the window is reported like any other word.
- The checker is a heuristic aid: not every repetition is a mistake, and the final judgement is the author's.
