import hashlib
import time
from pathlib import Path
import numpy as np
from .audio import read_audio, features, rms, waveform
from .common import read_json, write_json
from .model import tensorflow, build

def load_split(metadata, split):
    cfg = metadata["config"]
    rows = [r for r in metadata["rows"] if r["split"] == split]
    x,y,energy = [],[],[]
    for r in rows:
        audio,rate = read_audio(r["path"])
        x.append(features(audio,rate,cfg))
        energy.append(rms(waveform(audio,rate,cfg)))
        y.append(cfg["classes"].index(r["label"]))
    return np.asarray(x,dtype=np.float32), np.asarray(y), np.asarray(energy)

def dataset(tf,x,y,batch,shuffle=False,seed=42):
    ds=tf.data.Dataset.from_tensor_slices((x,y))
    if shuffle:
        ds=ds.shuffle(len(y),seed=seed)
    options=tf.data.Options(); options.threading.private_threadpool_size=1
    return ds.batch(batch).with_options(options).prefetch(1)

def train(cfg, smoke=False):
    meta=read_json("data/metadata/partitions.json")
    if meta["config"] != cfg:
        raise ValueError("La configuración cambió: vuelve a ejecutar prepare")
    tf=tensorflow(cfg)
    x,y,_=load_split(meta,"train"); vx,vy,ve=load_split(meta,"validation")
    if smoke:
        # Submuestra estratificada exclusivamente para detectar errores de ejecución.
        indices=np.concatenate([np.flatnonzero(y==i)[:16] for i in range(len(cfg["classes"]))])
        x,y=x[indices],y[indices]
    out=Path("models/smoke" if smoke else "models/full"); out.mkdir(parents=True,exist_ok=True)
    model=build(tf,x.shape[1:],len(cfg["classes"]),x.mean(dtype=np.float64),x.var(dtype=np.float64))
    model.summary()
    start=time.monotonic()
    history=model.fit(dataset(tf,x,y,cfg["batch_size"],True,cfg["seed"]),
        validation_data=dataset(tf,vx,vy,cfg["batch_size"]), epochs=1 if smoke else cfg["epochs"],
        callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss",patience=cfg["patience"],restore_best_weights=True),
                   tf.keras.callbacks.ModelCheckpoint(str(out/"best.keras"),monitor="val_loss",save_best_only=True)],verbose=2)
    model=tf.keras.models.load_model(out/"best.keras")
    p=model.predict(dataset(tf,vx,vy,cfg["batch_size"]),verbose=0)
    # Selección SOLO en validación: precisión selectiva >=.95 con >=30 aceptaciones.
    choices=[]
    for threshold in np.arange(.5,.991,.01):
        accepted=(p.max(1)>=threshold)&(ve>=cfg["silence_rms"])
        count=int(accepted.sum())
        precision=float((p.argmax(1)[accepted]==vy[accepted]).mean()) if count else None
        choices.append({"threshold":round(float(threshold),2),"accepted":count,"precision":precision})
    eligible=[c for c in choices if c["accepted"]>=30 and c["precision"]>=.95]
    selected=max(eligible,key=lambda c:c["accepted"]) if eligible else None
    threshold=selected["threshold"] if selected else .99
    write_json(out/"inference.json",{"config":cfg,"threshold":threshold,
        "threshold_status":"validation_selected" if selected else "conservative_fallback_target_not_met",
        "silence_status":"engineering_default_not_calibrated_on_noise", "validation_grid":choices,
        "metadata_sha256":hashlib.sha256(Path("data/metadata/partitions.json").read_bytes()).hexdigest()})
    write_json(out/"history.json",history.history)
    write_json(out/"run.json",{"smoke":smoke,"seconds":time.monotonic()-start,"epochs":len(history.epoch),
        "train_samples":len(y),"validation_samples":len(vy),"parameters":model.count_params(),"tensorflow":tf.__version__})
    # Verifica serialización sobre los mismos ejemplos.
    again=tf.keras.models.load_model(out/"best.keras")
    np.testing.assert_allclose(model(vx[:2],training=False).numpy(),again(vx[:2],training=False).numpy(),atol=1e-6)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(10,4))
    for axis,key in zip(ax,("loss","accuracy")):
        axis.plot(history.history[key],label="train");axis.plot(history.history["val_"+key],label="validation")
        axis.set_title(key);axis.set_xlabel("Época (índice desde 0)");axis.legend()
    fig.tight_layout(); fig.savefig(out/"curves.png");plt.close(fig)
    print("Guardado y carga verificados:",out)
