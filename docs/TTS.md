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
| `Qwen3:Design`   | see below |

`Qwen3:Design` uses the Qwen3 *VoiceDesign* model: there is no preset speaker, and the voice is described in natural language by the instruct string (see *Instruct config* below). Instruct keys are shared by all Qwen3 voices (`Qwen3.<instruct>`), so give voice descriptions their own instruct names, e.g. `Qwen3.narratrice: A warm, low female voice in her fifties, speaking slowly.` Lines without an explicit instruct use `Qwen3.default`.

#### Example: designed voices

The following script creates a voices config, an instruct config and a short text with two characters, each with its own designed voice, and renders them:

```bash
#!/bin/bash
mkdir -p design-example && cd design-example

cat > voices.conf <<'EOF'
Narratrice:   Qwen3:Design
Vecchio:      Qwen3:Design
EOF

cat > instruct.conf <<'EOF'
Qwen3.narratrice:  A warm, low female voice in her fifties, calm and slow, like an audiobook narrator.
Qwen3.vecchio:     An old man with a hoarse, slightly trembling voice, speaking slowly.
EOF

cat > test.txt <<'EOF'
[Narratrice, narratrice]: La sera scendeva lenta sulla valle, e nessuno aveva voglia di parlare.
[Vecchio, vecchio]: Ai miei tempi queste cose non succedevano, ve lo dico io.
EOF

BookAssistant tts test.txt --voices-config voices.conf --instruct-config instruct.conf --output design.wav
afplay design.wav    # macOS; elsewhere, use any audio player
```

Each tag names the character, which the voices config maps to `Qwen3:Design`, and the instruct whose text describes the voice. Lines without a tag belong to the `default` speaker, which must then be mapped as well. Every line is generated independently, so the same description gives similar but not necessarily identical voices from one line to the next. The VoiceDesign model (1.7B) is downloaded on first use, separately from the model used by the preset voices.


### Voxtral voices

Voxtral-4B-TTS (Mistral), running locally via MLX: **Apple Silicon only**. The model (about 3.5 GB) is released under CC BY-NC 4.0, i.e. for non-commercial use only.

| Name                    | Preset voice      | Accent  |
|-------------------------|-------------------|---------|
| `Voxtral:Male`          | `it_male`         | Italian |
| `Voxtral:Female`        | `it_female`       | Italian |
| `Voxtral:FrMale`        | `fr_male`         | French  |
| `Voxtral:FrFemale`      | `fr_female`       | French  |
| `Voxtral:CasualMale`    | `casual_male`     | English |
| `Voxtral:CasualFemale`  | `casual_female`   | English |
| `Voxtral:NeutralMale`   | `neutral_male`    | English |
| `Voxtral:NeutralFemale` | `neutral_female`  | English |
| `Voxtral:Cheerful`      | `cheerful_female` | English |

Any preset voice can read text in any language: a French voice reading Italian text speaks Italian with a French accent, which is useful for foreign characters. Voxtral ignores instruct strings, and custom voice cloning is not available.

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

This form is used on Apple Silicon Macs (MLX backend). On the other platforms (PyTorch backend) the value must instead be a `.pkl` voice-clone prompt, and no `@ref` entry is needed:

```
MyVoice:         path/to/MyVoice.pkl
```

A `.pkl` prompt can be created with the `CloneVoice` script in the repository root, which always uses the PyTorch backend:

```bash
./CloneVoice clone --csv samples/catalog.csv --csv-ref-audio voice01.wav --voice-name MyVoice.pkl --text "Testo di prova." --output test.wav
./CloneVoice test --voice-name MyVoice.pkl --text "Un'altra prova." --output test2.wav
```

The `--csv` catalog has one line per recording, with `|`-separated fields: the line mentioning the `--csv-ref-audio` file is used, its third field is the transcript, and the audio path is relative to the catalog's folder. If the transcript is empty, the recording is transcribed automatically with Qwen3-ASR. `clone` saves the prompt and renders `--text` as a test; `test` only renders the test. The script requires the `qwen-asr` package, which is not installed by `make venv-prepare`.

### Extra Qwen3 models (`--qwen3-model-config`)

Registers additional HuggingFace checkpoints compatible with Qwen3-TTS-CustomVoice (for example fine-tuned versions) as new voices:

```
MyFineTune:      someuser/Qwen3-TTS-CustomVoice-finetune
```

This registers the voice as `Qwen3:MyFineTune`, which speaks with the checkpoint's default speaker. The same repository id is used for both the MLX and the PyTorch backends, so the checkpoint must be in the format of the backend in use, and it must expose the same API as the official CustomVoice models.

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
| `--qwen3-model-config <file>`   | Extra Qwen3 checkpoints (name: HF repo id). Repeatable.                 |
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