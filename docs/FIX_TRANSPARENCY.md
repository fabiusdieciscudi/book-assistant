# Transparency Fixer

BookAssistant's `fix-transparency` command cleans up `.png` illustrations whose "empty" areas carry a faint, unintended grey tint instead of being properly transparent.

---

## The Problem It Solves

Some image editors (Affinity Photo among them) can export a PNG with a technically valid alpha channel, where the vast majority of pixels in what looks like an empty/transparent area aren't actually fully transparent. Instead of alpha = 0, they carry a small residual alpha value (for example, 1-50 out of 255) over black RGB data left over from how the artwork was rendered.

That residual is invisible while editing — a dark image-editor canvas or a near-black viewer background masks it completely. But once the PNG is composited over a light background (a white page in a LaTeX-generated PDF, for instance), that faint leftover opacity blends in just enough black to produce a visible grey rectangle across the whole illustration area, even though the image "looked" transparent in the editor.

This is not a bug in the PDF engine or in the viewer — the PNG file itself encodes that residual tint.

---

## Basic Usage

```bash
BookAssistant fix-transparency <path>
```

`<path>` can be a single `.png` file or a folder. When a folder is given, all `.png` files in it (including subdirectories) are processed in alphabetical order, each overwritten in place.

```bash
BookAssistant fix-transparency illustrations/
```

To process a single file and write the result elsewhere instead of overwriting it, use `--output`:

```bash
BookAssistant fix-transparency cover.png --output cover_fixed.png
```

`--output` can only be used when `<path>` is a single file. Using it with a folder is rejected, since multiple input files cannot all be written to one output path.

---

## What It Does

For every PNG with an alpha channel, the command looks at each pixel's alpha value and forces it to 0 whenever it falls below a threshold (default: 30 out of 255). Pixels that are clearly opaque (the actual artwork) are left untouched. The result is an image where near-invisible alpha noise becomes properly, fully transparent.

If a file already has no alpha values between 0 and the threshold — i.e. running the command would change nothing — it is left untouched on disk and reported as "already clean". This applies whether overwriting in place or writing to a separate file with `--output`: no output file is created if there's nothing to fix.

PNG files without an alpha channel (`RGB`, greyscale, etc.) are left untouched and reported as skipped — there is no transparency to fix.

---

## Output

Progress and results are logged to the console:

```
Processing: illustrations/chapter01.png
Overwritten: chapter01.png
Processing: illustrations/cover.png
WARNING: cover.png: no alpha channel (mode=RGB) - skipped.
Processing: illustrations/back-cover.png
Already clean, no changes needed: back-cover.png
Fixed 1 image(s), 1 already clean, skipped 1 (no alpha channel).
```

With `--debug`, each file also reports how many pixels changed from residually-transparent to fully transparent:

```
chapter01.png: fully-transparent pixels 6943 (0.2%) -> 2229875 (53.2%), threshold=30
```

---

## Options

| Option              | Description                                                                                          |
|---------------------|-------------------------------------------------------------------------------------------------------|
| `--threshold <int>` | Alpha values (0-255) strictly below this are forced to 0 (default: 30).                              |
| `--output <file>`   | Write the result to a different file instead of overwriting the input. Only valid for a single file. |
| `--debug`            | Enable verbose logging, including per-file alpha statistics.                                          |

### Choosing a threshold

The default of 30 works well for illustrations with fine pencil/ink-style line work, where antialiasing leaves low but non-zero alpha values scattered across nominally empty areas. If a grey tint is still visible after running the command, try a higher threshold (e.g. `--threshold 50`). If parts of a soft, intentionally faint edge disappear, the threshold is too high — lower it.

---

## Notes

- The command only touches the alpha channel; RGB pixel values are never modified.
- Pixels with alpha at or above the threshold are left exactly as they were — including values between, say, 31 and 254 — so soft, intentional partial transparency (gentle fades, soft shadows) is preserved.
- Running the command twice on the same file (or once on an already-clean file) is a no-op: the second run detects nothing to change and does not touch the file on disk. This makes it safe to re-run over a whole illustrations folder repeatedly, e.g. as part of a build pipeline.
- This does not replace verifying the actual export settings in the source image editor; it's a safety net for files where the exported alpha channel doesn't quite match what the canvas preview suggested.