"""Audio helpers: "phone quality" simulation and a simple voice-energy check.

Gemini Live needs 16 kHz input and sends 24 kHz output (16-bit PCM, little-endian).
The browser already captures the mic at 16 kHz, so normal mode needs no conversion.

Phone mode (8 kHz) makes the audio sound like a real phone call, then brings it
back to the rate Gemini expects:

    16 kHz in -> band-pass 300-3400 Hz -> keep every 2nd sample (8 kHz)
              -> G.711 mu-law round trip -> back up to 16 kHz -> Gemini

The agent's 24 kHz output goes through the same steps (factor 3), so both
directions sound like a phone line, as in the Sarvam tester.

Each direction keeps a PhoneLine object, because the filters carry state from
one audio chunk to the next (otherwise every chunk boundary would click).
"""

import numpy as np

PHONE_RATE = 8000
VOICE_RMS_THRESHOLD = 0.015  # about -36 dBFS; above this a chunk counts as "caller speaking"


def pcm_to_float(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0


def float_to_pcm(samples: np.ndarray) -> bytes:
    return (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def rms(pcm: bytes) -> float:
    """Loudness of a PCM chunk, 0.0 (silence) to about 1.0 (full scale)."""
    x = pcm_to_float(pcm)
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


def _lowpass_taps(cutoff_hz: float, rate: int, numtaps: int = 101) -> np.ndarray:
    """Windowed-sinc low-pass filter coefficients (gain 1 at 0 Hz)."""
    n = np.arange(numtaps) - (numtaps - 1) / 2
    h = np.sinc(2 * cutoff_hz / rate * n) * np.hamming(numtaps)
    return h / h.sum()


class StatefulFIR:
    """An FIR filter that remembers the end of the previous chunk."""

    def __init__(self, taps: np.ndarray):
        self.taps = taps
        self.tail = np.zeros(len(taps) - 1, dtype=np.float64)

    def process(self, x: np.ndarray) -> np.ndarray:
        if x.size == 0:
            return x
        buf = np.concatenate([self.tail, x])
        self.tail = buf[-(len(self.taps) - 1):]
        return np.convolve(buf, self.taps, mode="valid")


def mulaw_roundtrip(x: np.ndarray, mu: int = 255) -> np.ndarray:
    """Encode to 8-bit mu-law (as on Indian/US phone lines) and decode again."""
    y = np.sign(x) * np.log1p(mu * np.abs(x)) / np.log1p(mu)
    q = np.round(y * 127) / 127
    return np.sign(q) * np.expm1(np.abs(q) * np.log1p(mu)) / mu


class PhoneLine:
    """Turns a PCM stream at `rate` (16000 or 24000) into phone-quality audio at the same rate."""

    def __init__(self, rate: int):
        if rate % PHONE_RATE:
            raise ValueError("rate must be a multiple of 8000")
        self.factor = rate // PHONE_RATE
        # Band-pass 300-3400 Hz = low-pass 3400 minus low-pass 300. It also stops
        # aliasing when we drop samples.
        self.band = StatefulFIR(_lowpass_taps(3400, rate) - _lowpass_taps(300, rate))
        # After putting zeros between samples, this low-pass smooths them back into a wave.
        self.smooth = StatefulFIR(_lowpass_taps(3600, rate) * self.factor)
        self.phase = 0  # which input sample is the next one we keep

    def process(self, pcm: bytes) -> bytes:
        x = self.band.process(pcm_to_float(pcm).astype(np.float64))
        # Down to 8 kHz: keep every `factor`-th sample, continuing across chunks.
        narrow = x[self.phase::self.factor]
        self.phase = (self.phase - len(x)) % self.factor
        narrow = mulaw_roundtrip(narrow)
        # Back up to the original rate: zeros in between, then smooth.
        wide = np.zeros(len(narrow) * self.factor)
        wide[::self.factor] = narrow
        return float_to_pcm(self.smooth.process(wide))
