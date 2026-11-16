"""Único procesamiento utilizado por preparación, archivos y micrófono."""
import math
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

def read_audio(path):
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    if not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Audio vacío o con valores no finitos")
    return audio, rate

def waveform(audio, rate, cfg):
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if x.ndim != 1 or not len(x) or not np.isfinite(x).all() or rate <= 0:
        raise ValueError("Audio inválido")
    target = cfg["sample_rate"]
    if rate != target:
        divisor = math.gcd(int(rate), target)
        x = resample_poly(x, target // divisor, int(rate) // divisor)
    # Ventana de un segundo: recorte centrado y relleno al final, sin alterar originales.
    size = cfg["samples"]
    if len(x) > size:
        start = (len(x) - size) // 2
        x = x[start:start + size]
    return np.pad(x, (0, max(0, size - len(x)))).astype(np.float32)

def spectrum(x, cfg):
    # STFT Hann sin centrado implícito: idéntica para todos los orígenes.
    length, step = cfg["frame_length"], cfg["frame_step"]
    frames = np.lib.stride_tricks.sliding_window_view(x, length)[::step]
    window = np.hanning(length + 1)[:-1].astype(np.float32)
    spec = np.abs(np.fft.rfft(frames * window, n=cfg["fft_length"]))
    return np.log1p(spec).astype(np.float32)[..., None]

def features(audio, rate, cfg):
    return spectrum(waveform(audio, rate, cfg), cfg)

def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
