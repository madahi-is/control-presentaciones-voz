from pathlib import Path
import threading
from .common import read_json
from .audio import features
from .model import tensorflow

class Predictor:
    def __init__(self,directory="models/full"):
        directory=Path(directory)
        self.lock=threading.Lock()
        self.info=read_json(directory/"inference.json")
        self.cfg=self.info["config"]
        tf=tensorflow(self.cfg)
        self.model=tf.keras.models.load_model(directory/"best.keras")

    def predict(self,audio,rate):
        x=features(audio,rate,self.cfg)
        with self.lock:
            p=self.model(x[None],training=False).numpy()[0]
        index=int(p.argmax())
        return self.cfg["classes"][index],float(p[index])
