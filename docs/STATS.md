# Manuscript Statistics

BookAssistant's `stats` command prints a table of statistics for each chapter of a manuscript: length, sentence and paragraph structure, and two readability indexes. Optionally, it adds page counts taken from a LaTeX table of contents.

---

## Basic Usage

```bash
BookAssistant stats <path>
BookAssistant stats <path> --latex-toc book.toc
```

`<path>` can be a single `.txt` file or a folder. When a folder is given, all `.txt` files in it (including subdirectories) are analysed, and a single table with one row per file is printed at the end.

---

## Input Conventions

- The **first line** of each file is the chapter title. It is shown in the table and excluded from all counts.
- Every other non-empty line is a **paragraph**.
- `@language` tags (see [SPELLCHECK.md](SPELLCHECK.md)) are removed before counting words and sentences.

---

## Columns

| Column     | Meaning                                                                                                        |
|------------|----------------------------------------------------------------------------------------------------------------|
| `Chapter`  | Chapter title, without a leading `Capitolo N`, `Chapter N`, `Chapitre N`, `Parte`, `Part` or `Partie`; truncated to 40 characters. |
| `Words`    | Whitespace-separated tokens.                                                                                   |
| `Sent.`    | Sentences: runs of `.`, `!`, `?` or `…`. A paragraph not ending with one of them counts as one more sentence. |
| `Para.`    | Paragraphs.                                                                                                    |
| `Chars`    | Characters, spaces included.                                                                                   |
| `Cartelle` | Italian editorial unit: 1 cartella = 1,800 characters, spaces included.                                        |
| `W/S`      | Average words per sentence.                                                                                    |
| `W/P`      | Average words per paragraph.                                                                                   |
| `Gulpease` | Gulpease readability index, designed for Italian: 89 − 10 × chars/words + 300 × sentences/words.               |
| `Coleman`  | Coleman-Liau index, a grade-level estimate calibrated for English: treat it as approximate.                    |

When more than one file is processed, a `TOTAL` row is added. Its ratios and indexes are computed on the summed counts, not averaged across chapters.

### Colours

- **Gulpease**: red below 40, yellow from 40 to 60, green from 60 upward.
- **W/S** and **W/P**: red when more than one standard deviation above the average of all chapters, green when more than one standard deviation below it. The `TOTAL` row is never coloured.

---

## Page Columns (`--latex-toc`)

With `--latex-toc`, the command reads chapter and part entries from a LaTeX `.toc` file and matches them with the chapter titles. These columns are added:

| Column  | Meaning                                                    |
|---------|------------------------------------------------------------|
| `From`  | First page of the chapter.                                 |
| `Pages` | Number of pages, up to the start of the next `.toc` entry. |
| `Prog.` | Cumulative page count, with its percentage of the total.   |
| `S/Pg`  | Sentences per page.                                        |
| `W/Pg`  | Words per page.                                            |

Rows are then sorted in table-of-contents order; chapters not found in the `.toc` file go last. Without `--latex-toc`, rows are sorted by title, with numbers compared numerically (*Capitolo 2* comes before *Capitolo 10*).

Matching is case-insensitive and ignores differences in whitespace and in straight/curly apostrophes. LaTeX commands such as `\numberline`, `\hspace`, `\foreignlanguage` and `\xspace`, and leading roman numerals in part titles, are removed from the `.toc` titles first. If no exact match is found, a title contained in the other is accepted.

The `.toc` entries must have the four-argument form written when `hyperref` is loaded (`\contentsline{chapter}{…}{page}{chapter.N}`). The last entry has no following entry, so its page count is shown as `–`.

---

## Output

The table is printed to stdout at the end of the run, drawn with box characters. Progress messages go to stderr.

---

## Options

| Option               | Description                                     |
|----------------------|-------------------------------------------------|
| `--latex-toc <file>` | LaTeX `.toc` file used to add the page columns. |
| `--debug`            | Enable verbose logging.                         |

---

## Notes

- `Chars` is measured on the original lines, so it includes `@language` tags, unlike `Words` and `Sent.`.
- The canonical Gulpease index counts letters only; here characters include spaces and punctuation, so values come out lower than those found in the literature. Compare chapters with each other rather than with external reference values.
- A paragraph ending with a closing quote after the punctuation (e.g. `«Vieni qui.»`) counts one extra sentence, because its last character is not a sentence terminator.
- Abbreviations such as *Sig.* or *p.es.* are counted as sentence ends.
