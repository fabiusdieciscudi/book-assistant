# Text-to-Speech (TTS)

BookAssistant's `tts` command converts `.txt` files into audio, supporting multiple voices, multi-speaker narration, voice instructions, and word-level pronunciation patches.

---

## Basic Usage

```bash
python BookAssistant.py tts <path> --output <file.wav>
```

`<path>` can be a single `.txt` file or a folder. When a folder is given, all `.txt` files in it (including subdirectories) are processed in alphabetical order.

If `--output` is omitted, the audio is written to **stdout** (useful for piping).

---

## Input File Format

### Plain narration

Lines without any special markup are read by the default voice:

```
Nel mezzo del cammin di nostra vita mi ritrovai per una selva oscura.
```

### Speaker tags

To assign lines to a specific speaker, prefix them with a speaker tag:

```
[Narrator]: Nel mezzo del cammin di nostra vita.
[Beatrice]: Temo che tu non voglia udir le nuove.
[Virgilio, grave]: Seguimi, e lascia dir le genti.
```

The format is:

```
[<speaker>]: <line>
[<speaker>, <instruct>]: <line>
```

- `<speaker>` maps to a voice defined in the voices config file.
- `<instruct>` is an optional modifier that maps to an entry in the instruct config file, allowing you to adjust delivery (e.g. `grave`, `whisper`, `excited`) per line without changing the speaker.

### Pauses

Blank lines and lines containing only `***` produce a silence pause in the output:

```
Virgilio si fermò.

***

Poi riprese a parlare.
```

### Comments

Lines starting with `#` are ignored entirely:

```
# TODO: re-record this section
[Narrator]: Tanto gentile e tanto onesta pare.
```

### Long lines

Lines exceeding a voice's word limit are automatically split on sentence boundaries (`.`, `;`, `:`, `!`, `?`, `…`) before rendering.

---

## Voices

The following voices are available by name in config files.

### macOS voices (Italian)

| Name             | Voice                 |
|------------------|-----------------------|
| `MacOS:Federica` | Federica (Premium)    |
| `MacOS:Luca`     | Luca (Enhanced)       |
| `MacOS:Paola`    | Paola (Enhanced)      |
| `MacOS:Emma`     | Emma (Premium)        |
| `MacOS:Alice`    | Alice (Enhanced)      |
| `MacOS:Siri`     | Siri (system default) |

### Piper voices (Italian)

| Name             | Voice                |
|------------------|----------------------|
| `Piper:Riccardo` | it_IT-riccardo-x_low |
| `Piper:Paola`    | it_IT-paola-medium   |
| `Piper:Aurora`   | it_IT-aurora-medium  |

### Qwen3 voices (Italian)

Neural voices running locally via MLX (Apple Silicon) or PyTorch. See [Qwen3 Generation Parameters](#qwen3-generation-parameters) for tuning options.

| Name             | Character |
|------------------|-----------|
| `Qwen3`          | Default   |
| `Qwen3:Aiden`    | Aiden     |
| `Qwen3:Dylan`    | Dylan     |
| `Qwen3:Eric`     | Eric      |
| `Qwen3:Ono Anna` | Ono Anna  |
| `Qwen3:Ryan`     | Ryan      |
| `Qwen3:Serena`   | Serena    |
| `Qwen3:Sohee`    | Sohee     |
| `Qwen3:Uncle Fu` | Uncle Fu  |
| `Qwen3:Vivian`   | Vivian    |

### Other voices

| Name           | Engine           |
|----------------|------------------|
| `AzzurraVoice` | AzzurraVoice TTS |
| `Sibilia`      | Sibilia TTS      |

---

## Configuration Files

All configuration files are plain text key-value files (one `key: value` per line). Multiple files of the same type can be provided and are merged in order.

### Voices config (`--voices-config`)

Maps speaker names (as used in `[speaker]:` tags) to voice names:

```
Narrator:   Qwen3:Serena
Beatrice:   Qwen3:Vivian
Virgilio:   MacOS:Luca
default:    Qwen3:Serena
```

The special speaker name `default` is used for lines without a speaker tag.

A speaker+instruct variant can also be mapped directly:

```
Virgilio.grave:  Qwen3:Uncle Fu
```

This takes precedence over the plain `Virgilio` mapping when the instruct is `grave`.

### Instruct config (`--instruct-config`)

Maps `<voice_prefix>.<instruct>` keys to instruction strings passed to the TTS engine:

```
Qwen3.grave:     Speak in a deep, solemn tone.
Qwen3.whisper:   Speak very softly, almost whispering.
Qwen3.excited:   Speak with energy and enthusiasm.
```

The key prefix must match the TTS engine prefix (e.g. `Qwen3`, `MacOS`, `Piper`).

### Qwen3 clone config (`--qwen3-clone-config`)

Defines custom Qwen3 voices cloned from a reference audio file:

```
MyVoice:         path/to/reference.wav
MyVoice@ref:     The reference text spoken in the audio file.
```

This registers the voice as `Qwen3:MyVoice` and makes it available in the voices config like any built-in voice.

### Word patches (`--word-patches`)

Substitutions applied to every line before rendering, useful for correcting mispronunciations:

```
LOTR:           Lord of the Rings
J.R.R.:         J R R
```

Patches are applied in definition order.

---

## Qwen3 Generation Parameters

The `--qwen3-params` flag controls how the Qwen3 model samples audio tokens. It applies uniformly to all Qwen3 voices in the session, including cloned voices.

### Quick start: the `audiobook` preset

```bash
python BookAssistant.py tts chapter.txt --qwen3-params audiobook --output chapter.wav
```

This is the recommended starting point for narration. It enables sampling with community-tested values:

| Parameter            | Value   |
|----------------------|---------|
| `temperature`        | 0.9     |
| `top_p`              | 1.0     |
| `top_k`              | 50      |
| `repetition_penalty` | 1.05    |

### Individual parameters

Parameters can be set individually using `key:value` pairs:

```bash
python BookAssistant.py tts chapter.txt \
    --qwen3-params temperature:0.8 \
    --qwen3-params repetition_penalty:1.05 \
    --output chapter.wav
```

#### Talker parameters (semantic stage)

These control the first stage of generation, which converts text into prosody and rhythm tokens.

| Key                  | Type  | Description                                                                                                                                                                                                                                                                   agar         |
|----------------------|-------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `temperature`        | float | Sampling temperature. Lower values (e.g. `0.3`) produce more predictable, monotone speech; higher values (e.g. `1.2`) add expressiveness but risk instability. `0.9` is a good starting point. Without this flag, the model defaults to greedy (deterministic) decoding for preset voices. |
| `top_p`              | float | Nucleus sampling threshold. Only tokens whose cumulative probability reaches this value are considered. `1.0` disables filtering; `0.9` trims the long tail of unlikely tokens.                                                                                                            |
| `top_k`              | int   | Limits sampling to the top-k most probable tokens at each step. `50` is a typical value.                                                                                                                                                                                                   |
| `repetition_penalty` | float | Penalises recently generated tokens, reducing the chance of repeated syllables or stuck loops. `1.05`–`1.1` is recommended; `1.0` disables it.                                                                                                                                             |
| `max_tokens`         | int   | Maximum number of tokens the model may generate for a single chunk. Rarely needs changing; the default is 2048.                                                                                                                                                                            |

#### SubTalker parameters (acoustic stage)

Qwen3-TTS has a second stage that converts semantic tokens into acoustic tokens. By default it mirrors the talker settings above. Override only if you want the two stages to behave differently.

| Key                     | Type  | Description                                    |
|-------------------------|-------|------------------------------------------------|
| `subtalker_temperature` | float | Temperature for the acoustic stage only.       |
| `subtalker_top_p`       | float | Nucleus threshold for the acoustic stage only. |
| `subtalker_top_k`       | int   | Top-k for the acoustic stage only.             |

#### Speed (MLX backend only)

| Key     | Type  | Description                                                                                      |
|---------|-------|--------------------------------------------------------------------------------------------------|
| `speed` | float | Playback speed multiplier. `1.0` is normal; `1.2` is 20% faster. Ignored on the PyTorch backend. |

### Notes on sampling

When no `--qwen3-params` flag is given, the behaviour depends on the voice type:

- **Preset voices** (`Qwen3:Serena`, etc.): greedy decoding — deterministic but tends to sound flat.
- **Cloned voices** (`.wav` / `.pkl`): the PyTorch backend uses sampling with `temperature=0.65, top_p=0.90` by default; the MLX backend defers to the library default.

Passing any sampling parameter (e.g. `temperature:0.9`) switches all Qwen3 voices to sampling mode for that session.

---

## Output Formats

| Format        | Option         |
|---------------|----------------|
| WAV (default) | `--format WAV` |
| MP3           | `--format MP3` |

For MP3, use `--compression` to set the quality level (0–99, default 0 = highest quality).
If you need more advanced encoding options, output a WAV and convert with `ffmpeg`.

---

## Options

| Option                          | Description                                                             |
|---------------------------------|-------------------------------------------------------------------------|
| `--output <file>`               | Output file path. Defaults to stdout.                                   |
| `--format <fmt>`                | Output format: `WAV` or `MP3` (default: `WAV`).                         |
| `--compression <n>`             | Compression level 0–99 for MP3 (default: `0`).                          |
| `--voices-config <file>`        | Speaker-to-voice mapping. Repeatable.                                   |
| `--instruct-config <file>`      | Voice instruction mapping. Repeatable.                                  |
| `--qwen3-clone-config <file>`   | Qwen3 cloned voice definitions. Repeatable.                             |
| `--qwen3-params <key:value>`    | Qwen3 generation parameter or `audiobook` preset. Repeatable.           |
| `--word-patches <file>`         | Word-level pronunciation patches. Repeatable.                           |
| `--max-loaded-models <n>`       | Maximum number of voices to keep in memory simultaneously (default: 5). |
| `--max-lines <n>`               | Stop after processing this many lines (default: all).                   |
| `--dry-run`                     | Validate speaker/voice assignments without rendering audio.             |
| `--debug`                       | Enable verbose logging.                                                 |

---

## Notes

- All audio is resampled to a common sample rate (22050 Hz) before being concatenated.
- A short silence is inserted between every line; longer pauses are inserted for blank lines and `***` lines.
- The input file is always validated before rendering begins, so speaker/voice errors are caught upfront.
- Character translations are applied automatically: curly quotes become straight quotes, `…` becomes `...`.
- Models are downloaded from HuggingFace on first use and cached locally; subsequent runs work fully offline.