# Guillemet Checker

BookAssistant's `check-guillemets` command scans `.txt` files for likely punctuation errors around closing guillemets (`»`), flagging cases where the punctuation placement looks inconsistent or wrong.

Note: this is just one of the many punctuation conventions for guillemets.
It's the one used by the tool author.

---

## Basic Usage

```bash
python BookAssistant.py check-guillemets <path>
```

`<path>` can be a single `.txt` file or a folder. When a folder is given, all `.txt` files in it (including subdirectories) are processed in alphabetical order.

---

## What It Checks

The implemented typographic convention places punctuation **outside** guillemets — the closing `»` comes before any comma, period, or other punctuation mark. 
The checker looks for two categories of suspicious patterns around `»`:

### 1. Punctuation on both sides

If there is a punctuation character immediately **before** `»` and also immediately **after** it, that is likely a double-punctuation error:

```
# Flagged: punctuation appears both before and after »
«Vieni qui!».         ← the period after » is redundant
```

### 2. Inconsistent punctuation before a continuation word

When `»` is followed by a continuation word (typically a dialogue attribution verb such as *disse*, *rispose*, etc.), the checker examines whether a separating punctuation mark is present or absent between the guillemet and the word, and flags cases that look inconsistent.

---

## Output

Flagged lines are printed to the console with the suspicious segment highlighted in red:

```
chapter01.txt: «Vieni qui»[,] disse lui.
```

The file name is shown at the start of each line. No output means no issues were found.

---

## Options

This command has no additional options beyond the global ones.

| Option    | Description             |
|-----------|-------------------------|
| `--debug` | Enable verbose logging. |

---

## Notes

- The checker operates entirely on typographic heuristics and may produce false positives in edge cases, particularly with unusual sentence structures.
- Only the closing guillemet `»` is analysed; opening guillemets `«` are not checked.
- The punctuation characters considered are: `. , ! ? ; : - — …`