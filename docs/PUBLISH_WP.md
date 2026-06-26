# WordPress Publisher

BookAssistant's `publish-wp` command uploads HTML chapters, as produced from LaTeX sources by TeX4ht/make4ht, to **existing** WordPress pages through the WordPress REST API. It is meant for serialising a book on a website: the pages are created once in WordPress, and the command keeps their content in sync with the local files.

---

## Basic Usage

```bash
export WP_USER=author
export WP_PASSWORD='abcd efgh ijkl mnop qrst uvwx'
BookAssistant publish-wp chapters/ --wp-url 'https://example.com/book/c{n}'
```

`<path>` can be a single `.html` file or a folder. When a folder is given, all `.html` files in it (including subdirectories) are processed in alphabetical order.

---

## Prerequisites

- The WordPress REST API must be reachable at `https://<host>/wp-json/wp/v2/`. The site is assumed to be installed at the root of the host.
- Every target page must already exist: the command updates pages, it never creates them.
- The user needs an *Application Password*, generated under **Users → Profile → Application Passwords**. Application Passwords are not subject to two-factor authentication.

---

## How It Works

For each `.html` file:

1. The `--slug-pattern` regular expression is searched in the file name (without extension). Its first group is the chapter number. Files that do not match are skipped with a warning.
2. The chapter number replaces `{n}` in `--wp-url`. The last path segment of the resulting URL is the page slug: with the example above, `ch3.html` becomes `https://example.com/book/c3`, slug `c3`.
3. The page is looked up by slug, whatever its status (published, draft, …). If it does not exist, an error is reported.
4. If the local file is not newer than the page's last modification in WordPress, it is skipped.
5. Otherwise the HTML is cleaned (see below) and replaces the page content.

Because the comparison uses the file modification time, touching a file forces it to be published again on the next run.

---

## HTML Cleaning

Before upload, TeX4ht boilerplate is removed and the content is converted to Gutenberg blocks:

- **Removed:** `<head>`, HTML comments, the `crosslinks` navigation, `<h2>` (the chapter title, already set in WordPress), empty anchors, footnote marks and every `id` attribute. `<br>` is replaced by a space, and paragraphs left empty are dropped.
- **Converted to `<i>`:** spans with the TeX classes `ec-lmri-*` (italic), `ec-lmbx-*` (bold extended) and `small-caps`.
- **Unwrapped:** all other `<span>` elements, whose text is kept.
- **Wrapped in blocks:** `<p>` becomes `wp:paragraph`, `<blockquote>` becomes `wp:quote`, and the footnotes `<div>` becomes an empty `wp:footnotes` block.

Only paragraphs, blockquotes and the footnotes block at the top level of the body are kept; any other top-level element (lists, tables, other headings, `div`s) is dropped.

---

## Output

```
ch3.html  →  https://example.com/book/c3
  Published (id=1234).
ch4.html  →  https://example.com/book/c4
  Skipped: file is not newer than the WP page (2026-06-20T10:00:00+00:00 ≤ 2026-06-21T08:30:00+00:00).
Published: 1  |  Skipped: 1  |  Errors: 0
```

---

## Options

| Option                     | Description                                                                                 |
|----------------------------|---------------------------------------------------------------------------------------------|
| `--wp-url <pattern>`       | Page URL pattern; `{n}` is replaced by the chapter number. Required.                        |
| `--slug-pattern <regex>`   | Regex applied to the file name; its first group is the chapter number (default: `ch(\d+)`). |
| `--wp-user <user>`         | WordPress user name. Defaults to the `WP_USER` environment variable.                        |
| `--wp-password <password>` | WordPress Application Password. Defaults to the `WP_PASSWORD` environment variable.         |
| `--dry-run`                | Look up the pages and report what would be published, without modifying anything.          |
| `--debug`                  | Enable verbose logging, including the REST calls and the dates being compared.             |

---

## Notes

- `--slug-pattern` is case-sensitive: the default `ch(\d+)` matches `ch3.html` but not `Ch3.html`. Use `(?i)ch(\d+)` to ignore case.
- Footnote texts are not transferred: the footnote marks are removed and the footnotes section is replaced by an empty `wp:footnotes` block, so footnotes must be managed in WordPress.
- In dry-run mode the pages that would be updated are counted as `Published` in the final summary. Credentials are still required, since the pages are looked up.
- Prefer the environment variables to `--wp-password`: a password on the command line ends up in the shell history.
