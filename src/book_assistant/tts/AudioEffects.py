"""Simple post-processing audio effects for speech: telephone, radio, echo and reverb.

Effects are named in English, Italian or French (accents and case don't matter), and
echo and reverb take an optional level from 1 to 3 (default 2), e.g. ``eco1``, ``reverb3``.
"""
import math
import re
import unicodedata

import numpy as np

_SYNONYMS: dict[str, set[str]] = {
    "phone":  {"phone", "telephone", "telefono"},                                     # FR: téléphone
    "radio":  {"radio", "transmitter", "walkietalkie", "trasmittente", "ricetrasmittente", "emetteur"},  # FR: émetteur
    "echo":   {"echo", "eco"},                                                        # FR: écho
    "reverb": {"reverb", "reverberation", "riverbero", "reverbero"},                  # FR: réverbération
}
_LEVELLED = {"echo", "reverb"}
_DEFAULT_LEVEL = 2
_EFFECT_BY_NAME = {name: effect for effect, names in _SYNONYMS.items() for name in names}

_ECHO_LEVELS = {        # delay (s), feedback, wet mix
    1: (0.12, 0.25, 0.25),
    2: (0.25, 0.35, 0.35),
    3: (0.40, 0.50, 0.45),
}
_REVERB_LEVELS = {      # RT60 (s), pre-delay (s), wet mix
    1: (0.4, 0.010, 0.20),
    2: (1.2, 0.020, 0.30),
    3: (2.5, 0.030, 0.40),
}


def _normalized_name(name: str) -> str:
    """Lowercases *name* and strips accents, spaces, dashes and underscores."""
    decomposed = unicodedata.normalize("NFKD", name.strip().lower())
    return re.sub(r"[\s_\-]", "", "".join(c for c in decomposed if not unicodedata.combining(c)))


def parse_effects(spec: str) -> list[tuple[str, int]]:
    """Parses an effect chain such as ``telefono+eco1``.

    :param spec:                    the effect names, separated by ``+``
    :return:                        the effects in order, as (canonical name, level) pairs
    """
    effects = []
    for raw in spec.split("+"):
        name = _normalized_name(raw)
        if not name:
            continue
        match = re.fullmatch(r"(.*?)([1-3])?", name)
        base, level = match.group(1), match.group(2)
        effect = _EFFECT_BY_NAME.get(base)
        if effect is None:
            valid = sorted(f"{e}[1-3]" if e in _LEVELLED else e for e in _SYNONYMS)
            raise ValueError(f"unknown effect '{raw.strip()}'. Valid: {valid} (also in Italian and French)")
        if level and effect not in _LEVELLED:
            raise ValueError(f"effect '{raw.strip()}' has no levels")
        effects.append((effect, int(level) if level else (_DEFAULT_LEVEL if effect in _LEVELLED else 0)))
    if not effects:
        raise ValueError("no effect specified")
    return effects


def apply_effects(audio: np.ndarray, sample_rate: int, effects: list[tuple[str, int]]) -> np.ndarray:
    """Applies an effect chain, in order, to a mono waveform.

    Echo and reverb make the result longer than the input: the extra samples are the tail.

    :param audio:                   the mono waveform
    :param sample_rate:             its sample rate
    :param effects:                 the effects, as returned by :func:`parse_effects`
    :return:                        the processed waveform
    """
    if audio.size == 0:
        return audio
    out = audio.astype(np.float32)
    for effect, level in effects:
        if effect == "phone":
            out = _phone(out, sample_rate)
        elif effect == "radio":
            out = _radio(out, sample_rate)
        elif effect == "echo":
            out = _echo(out, sample_rate, *_ECHO_LEVELS[level])
        elif effect == "reverb":
            out = _reverb(out, sample_rate, *_REVERB_LEVELS[level])
    peak = float(np.max(np.abs(out)))
    if peak > 0.99:
        out = out * (0.99 / peak)
    return out.astype(np.float32)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0


def _bandpass(x: np.ndarray, sample_rate: int, low: float, high: float, order: int = 4) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    high = min(high, 0.45 * sample_rate)
    sos = butter(order, [low, high], btype="bandpass", fs=sample_rate, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def _match_loudness(processed: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Scales *processed* to the RMS level of *reference*, so a filter doesn't make the voice quieter."""
    rms = _rms(processed)
    return processed * (_rms(reference) / rms) if rms > 0 else processed


def _saturate(x: np.ndarray, drive: float) -> np.ndarray:
    peak = float(np.max(np.abs(x))) or 1.0
    return (np.tanh(drive * x / peak) / math.tanh(drive) * peak).astype(np.float32)


def _noise(length: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(length).astype(np.float32)


def _phone(x: np.ndarray, sample_rate: int) -> np.ndarray:
    """A good-quality phone line: 280-4000 Hz band with gentle slopes, a small presence bump
    around 2 kHz (the typical earpiece colour) and a hint of saturation. No quantisation noise."""
    from scipy.signal import sosfilt
    y = _bandpass(x, sample_rate, 280, 4000, order=3)
    y = y + 0.35 * sosfilt(_peak_sos(sample_rate, 2000, 1.0), y).astype(np.float32)
    y = _saturate(y, 1.2)
    return _match_loudness(y.astype(np.float32), x)


def _peak_sos(sample_rate: int, centre: float, octaves: float):
    """A band-pass of the given width, used to add a resonance around *centre*."""
    from scipy.signal import butter
    low, high = centre / 2 ** (octaves / 2), centre * 2 ** (octaves / 2)
    return butter(2, [low, min(high, 0.45 * sample_rate)], btype="bandpass", fs=sample_rate, output="sos")


def _radio(x: np.ndarray, sample_rate: int) -> np.ndarray:
    """Two-way radio: 500-2500 Hz band, strong saturation, background hiss and a squelch burst at both ends."""
    y = _match_loudness(_saturate(_bandpass(x, sample_rate, 500, 2500), 6.0), x)
    level = _rms(y) or 0.05
    hiss = _bandpass(_noise(len(y), seed=len(y)), sample_rate, 800, 5000)
    y = y + hiss / (_rms(hiss) or 1.0) * level * 0.08
    burst_len = int(0.08 * sample_rate)
    burst = _bandpass(_noise(burst_len, seed=burst_len), sample_rate, 600, 4000)
    burst = burst / (_rms(burst) or 1.0) * level * 0.6 * np.linspace(1.0, 0.0, burst_len, dtype=np.float32)
    return np.concatenate([burst[::-1], y, burst]).astype(np.float32)


def _echo(x: np.ndarray, sample_rate: int, delay: float, feedback: float, mix: float) -> np.ndarray:
    """Repeating echo: copies every *delay* seconds, each *feedback* times softer, until inaudible."""
    step = int(delay * sample_rate)
    repeats = max(1, math.ceil(math.log(0.01) / math.log(feedback)))
    out = np.zeros(len(x) + step * repeats, dtype=np.float32)
    out[:len(x)] += x
    for k in range(1, repeats + 1):
        out[k * step:k * step + len(x)] += x * (mix * feedback ** (k - 1))
    return out


def _reverb(x: np.ndarray, sample_rate: int, rt60: float, pre_delay: float, mix: float) -> np.ndarray:
    """Reverb by convolution with a synthetic impulse response: exponentially decaying, slightly darkened noise."""
    from scipy.signal import fftconvolve
    length = int(rt60 * sample_rate)
    t = np.arange(length, dtype=np.float32) / sample_rate
    ir = _noise(length, seed=length) * np.exp(-6.91 * t / rt60)          # -60 dB at rt60
    ir = _bandpass(ir, sample_rate, 80, 6000)
    ir = np.concatenate([np.zeros(int(pre_delay * sample_rate), dtype=np.float32), ir])
    wet = fftconvolve(x, ir).astype(np.float32)
    wet = wet * (_rms(x) / (_rms(wet[:len(x)]) or 1.0))
    out = wet * mix
    out[:len(x)] += x * (1.0 - mix * 0.5)
    return out
