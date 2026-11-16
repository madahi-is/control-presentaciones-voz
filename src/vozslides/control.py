"""Reglas de acciones independientes de TensorFlow y de la interfaz."""
from dataclasses import dataclass
ACTIONS = {"right":"next", "left":"previous", "go":"start", "stop":"finish"}
SPANISH_ACTIONS = {"siguiente":"next", "anterior":"previous", "iniciar":"start", "finalizar":"finish"}

def command_action(word, classes):
    """Solo permite acciones de etiquetas realmente entrenadas y guardadas."""
    if word not in classes:
        return None
    return {**ACTIONS, **SPANISH_ACTIONS}.get(word)

@dataclass
class Navigation:
    pages: int = 0
    index: int = 0
    presenting: bool = False

    def apply(self, action):
        if not self.pages:
            return False
        if action == "next":
            self.index = min(self.pages-1, self.index+1)
        elif action == "previous":
            self.index = max(0,self.index-1)
        elif action == "start":
            self.index, self.presenting = 0, True
        elif action == "finish":
            self.presenting = False
        else:
            return False
        return True

class Gate:
    def __init__(self, threshold, silence_rms=.008, cooldown=1.):
        self.threshold, self.silence_rms, self.cooldown = threshold, silence_rms, cooldown
        self.last = -float("inf")

    def accept(self, confidence, energy, now):
        if energy < self.silence_rms:
            return False, "silencio"
        if confidence < self.threshold:
            return False, "baja confianza"
        if now-self.last < self.cooldown:
            return False, "intervalo de seguridad"
        self.last=now
        return True, "aceptado"
