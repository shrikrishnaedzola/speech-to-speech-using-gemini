import numpy as np

from app.services.audio import PhoneLine, float_to_pcm, pcm_to_float, rms


def tone(freq, rate, seconds=1.0, amp=0.5):
    t = np.arange(int(rate * seconds)) / rate
    return float_to_pcm(amp * np.sin(2 * np.pi * freq * t))


def through_line(pcm: bytes, rate: int, chunk_samples: int) -> np.ndarray:
    """Send audio through a PhoneLine in chunks, like the live stream does."""
    line = PhoneLine(rate)
    step = chunk_samples * 2
    out = b"".join(line.process(pcm[i:i + step]) for i in range(0, len(pcm), step))
    return pcm_to_float(out)


def level(samples: np.ndarray) -> float:
    middle = samples[len(samples) // 4: -len(samples) // 4]  # skip filter warm-up
    return float(np.sqrt(np.mean(middle ** 2)))


def test_phone_line_keeps_voice_band_16k():
    out = through_line(tone(1000, 16000), 16000, 640)
    assert level(out) > 0.25  # a 1 kHz tone (voice band) passes; input level is ~0.35


def test_phone_line_removes_high_frequencies_16k():
    out = through_line(tone(6000, 16000), 16000, 640)
    assert level(out) < 0.02  # 6 kHz cannot pass an 8 kHz phone line


def test_phone_line_output_24k_with_odd_chunks():
    pcm = tone(1000, 24000)
    out = through_line(pcm, 24000, 1001)  # chunk size not a multiple of 3
    assert abs(len(out) - len(pcm) // 2) <= 3  # same length (stream continues across chunks)
    assert level(out) > 0.25
    assert level(through_line(tone(9000, 24000), 24000, 1001)) < 0.02


def test_rms():
    assert rms(b"\x00\x00" * 100) == 0.0
    assert 0.3 < rms(tone(440, 16000)) < 0.4
    assert rms(b"") == 0.0
