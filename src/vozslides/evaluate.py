import hashlib
from pathlib import Path
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, log_loss, confusion_matrix, ConfusionMatrixDisplay
from .common import read_json,write_json
from .model import tensorflow
from .train import load_split,dataset

def evaluate(model_dir="models/full"):
    directory=Path(model_dir)
    info=read_json(directory/"inference.json")
    digest=hashlib.sha256(Path("data/metadata/partitions.json").read_bytes()).hexdigest()
    if digest!=info["metadata_sha256"]:
        raise ValueError("Las particiones no coinciden con las usadas al entrenar")
    cfg=info["config"]; tf=tensorflow(cfg)
    model=tf.keras.models.load_model(directory/"best.keras")
    x,y,energy=load_split(read_json("data/metadata/partitions.json"),"test")
    p=model.predict(dataset(tf,x,y,cfg["batch_size"]),verbose=0); pred=p.argmax(1)
    pr,rc,f1,_=precision_recall_fscore_support(y,pred,labels=range(len(cfg["classes"])),average="macro",zero_division=0)
    accepted=(p.max(1)>=info["threshold"])&(energy>=cfg["silence_rms"])
    metrics={"n":len(y),"accuracy":accuracy_score(y,pred),"precision_macro":pr,"recall_macro":rc,"f1_macro":f1,
        "log_loss":log_loss(y,p,labels=range(len(cfg["classes"]))),"accepted":int(accepted.sum()),
        "selective_accuracy":float((pred[accepted]==y[accepted]).mean()) if accepted.any() else None,
        "threshold":info["threshold"],"warning":"Conjunto cerrado: no mide rechazo de palabras desconocidas"}
    out=Path("results")/directory.name;out.mkdir(parents=True,exist_ok=True)
    write_json(out/"metrics.json",metrics)
    np.savez_compressed(out/"predictions.npz",y=y,probabilities=p)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ConfusionMatrixDisplay(confusion_matrix(y,pred),display_labels=cfg["classes"]).plot(xticks_rotation=45)
    plt.tight_layout();plt.savefig(out/"confusion.png");plt.close()
    print(metrics)
