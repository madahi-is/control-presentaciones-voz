"""Segmentación energética independiente de PortAudio y de la interfaz."""
from collections import deque
import numpy as np
from .audio import rms


class Segmenter:
    def __init__(self, rate, threshold, release_ms=240, block_ms=40,
                 min_voice_ms=80, max_ms=1400):
        self.rate = rate
        self.threshold = threshold
        self.block_ms = block_ms
        self.release_blocks = max(1, int(np.ceil(release_ms / block_ms)))
        self.min_blocks = max(1, int(np.ceil(min_voice_ms / block_ms)))
        self.max_blocks = max(1, int(np.ceil(max_ms / block_ms)))
        self.reset()

    def reset(self):
        self.pre = deque(maxlen=3)
        self.parts = []
        self.quiet = self.voiced = 0
        self.locked = False

    def feed(self, chunk):
        silent = rms(chunk) < self.threshold
        if self.locked:
            self.quiet = self.quiet + 1 if silent else 0
            if self.quiet >= self.release_blocks:
                self.reset()
            return None
        if not self.parts:
            self.pre.append(chunk.copy())
            if silent:
                return None
            self.parts = list(self.pre)
            self.pre.clear()
            self.voiced = 1
        else:
            self.parts.append(chunk.copy())
            self.voiced += int(not silent)
        self.quiet = self.quiet + 1 if silent else 0
        forced = len(self.parts) >= self.max_blocks
        if self.quiet < self.release_blocks and not forced:
            return None
        # Conserva la duración original y el relleno final compartido con entrenamiento.
        parts = self.parts[:-self.quiet] if self.quiet else self.parts
        accepted = self.voiced >= self.min_blocks
        audio = np.concatenate(parts) if accepted and parts else None
        self.parts = []
        self.pre.clear()
        self.voiced = self.quiet = 0
        self.locked = forced
        return audio


def noise_threshold(levels, baseline):
    """Heurística de sesión, no umbral aprendido ni garantía frente a ruido."""
    values = np.asarray(levels, dtype=float)
    if not len(values) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("No hay niveles de ruido válidos")
    noise = float(np.percentile(values, 90))
    return max(float(baseline), noise * 2.5), noise
