# Spell Checker

BookAssistant's `spellcheck` command scans `.txt` files for spelling errors and typos using [LanguageTool](https://languagetool.org/). 
It supports multilingual documents, letting you annotate passages with language tags so each section is checked against the right language.

---

## Basic Usage

```bash
BookAssistant spellcheck <path>
```

`<path>` can be a single `.txt` file or a folder. When a folder is given, all `.txt` files in it (including subdirectories) are processed in alphabetical order.

---

## Supported Languages

Tag any passage with `@<language>` to switch the active language for everything that follows. The tag must appear as a standalone word (i.e. separated by spaces).

| Tag           | Language                    |
|---------------|-----------------------------|
| `@dutch`      | Dutch                       |
| `@english`    | English                     |
| `@french`     | French                      |
| `@german`     | German                      |
| `@irish`      | Irish                       |
| `@italian`    | Italian (default)           |
| `@latin`      | Latin (checked via Italian) |
| `@portuguese` | Portuguese                  |
| `@spanish`    | Spanish                     |
| `@swedish`    | Swedish                     |
| `@turkish`    | Turkish                     |

The default language is **Italian**. A bare `@` tag with no name resets to Italian.

### Example

```
Nel mezzo del cammin di nostra vita 
@english In the middle of the journey of our life
@italian mi ritrovai per una selva oscura
```

The first and third line are checked as Italian, the second as English.

---

## Custom Dictionaries

You can provide one or more custom dictionary files to suppress false positives for domain-specific words, proper nouns, or other known terms.

```bash
BookAssistant spellcheck <path> --dict my_dictionary.txt
BookAssistant spellcheck <path> --dict base.txt --dict extra.txt
```

### Dictionary File Format

A dictionary file is a plain UTF-8 text file. Lines starting with `#` are comments and are ignored. Words are grouped under language sections declared with `@<language>`:

```
# My custom dictionary

@italian
Bolgheri
Calafuria
brontidi
calette
camenèrio

@french
Bessillon
Boscodon
Brégançon
inforçable
patou
```

- Each `@language` line starts a new section; all words below it belong to that language until the next `@language` tag.
- One word per line.
- The language name must match the supported language names in the table above.

---

## Output

Errors are printed to the console in the format:

```
filename.txt[line]: 'language' 'misspelled_word' CATEGORY
```

For example:

```
chapter01.txt[42]: 'italian' 'aquisto' TYPOS
```

Progress is shown inline as each line is processed:

```
chapter01.txt[1/312]
```

---

## Options

| Option          | Description                                                                               |
|-----------------|-------------------------------------------------------------------------------------------|
| `--dict <file>` | Load a custom dictionary file. Can be repeated to load multiple files.                    |
| `--debug`       | Enable verbose logging.                                                                   |

---

## Notes

- Curly apostrophes (`'`) are normalised to straight apostrophes (`'`) before checking.
- Punctuation characters `.,!?;:—…()[]{}"""«»` are stripped from words before checking.
