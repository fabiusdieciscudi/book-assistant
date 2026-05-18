# HTML to Text Converter

BookAssistant's `html2txt` command converts an XHTML file to plain text, one paragraph per line. It is meant for chapters produced from LaTeX sources by TeX4ht/make4ht, so that the other commands (`spellcheck`, `echo`, `stats`, `tts`, …) can work on them.

---

## Basic Usage

```bash
BookAssistant html2txt chapter01.html
BookAssistant html2txt chapter01.html --output chapter01.txt
BookAssistant html2txt chapters/
BookAssistant html2txt chapters/ --output txt/
```

`<path>` can be a single `.html` file or a folder. When a folder is given, all `.html` files in it (including subdirectories) are converted in alphabetical order.

Without `--output`, each result is written next to its input file, with the same name and a `.txt` extension. With a folder, `--output` names a destination folder: each `.txt` keeps the name of its `.html` file and its position relative to `<path>`, and missing subfolders are created (`chapters/part2/ch07.html` becomes `txt/part2/ch07.txt`). With a single file, `--output` is the output file, or an existing folder to write it into. A file whose output would overwrite the input itself (for instance a `.txt` file passed by mistake) is skipped with an error.

---

## What It Does

1. The file is parsed as XML, so it must be well-formed XHTML (as produced by make4ht).
2. `script`, `style`, `noscript`, `header`, `footer`, `nav`, `aside` and `svg` elements are removed, together with their content.
3. Every block element — `p`, `h1`…`h6`, `li`, `dt`, `dd`, `div`, `section`, `article`, `blockquote`, `pre`, `tr` — becomes one line. Blocks nested inside another block become lines of their own, and their text is not repeated in the enclosing block.
4. Whitespace inside each line is collapsed to single spaces, and blocks with no text are dropped: the output contains no blank lines.
5. Typographic ligatures (`ﬀ`, `ﬁ`, `ﬂ`, `ﬃ`, `ﬄ`) are decomposed into plain letters.

The output file is written only if its content would change, so file modification times — and any build step depending on them — are left alone when the source is unchanged.

---

## Output

```
Creating /path/to/chapter01.txt...
```

or, when the existing file is already up to date:

```
/path/to/chapter01.txt is unchanged
```

---

## Options

| Option            | Description                                                         |
|-------------------|---------------------------------------------------------------------|
| `--output <path>` | Output file, or destination folder (see above).                     |
| `--debug`         | Enable verbose logging.                                             |

---

## Notes

- `--dry-run` has no effect on this command: the output file is always written when it differs.
- Inline formatting (italics, small caps, …) is discarded; only the text is kept.
- Text that is not inside one of the block elements listed above (for instance placed directly in `body`) is not included.
