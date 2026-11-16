"""Inventario auditable, duplicados y partición por componentes de hablantes."""
import csv
import hashlib
import re
from collections import Counter
from pathlib import Path
import numpy as np
from .audio import read_audio, waveform, spectrum
from .common import write_json

NAME = re.compile(r"^([A-Za-z0-9]+)_nohash_(\d+)\.wav$")

def speaker_id(path):
    match = NAME.fullmatch(Path(path).name)
    if not match:
        raise ValueError(f"Nombre incompatible: {path}; esperado ID_nohash_N.wav")
    return match.group(1)

def assign_splits(rows, seed):
    # Une hablantes vinculados por audios idénticos, incluso entre etiquetas.
    parents = {r["speaker"]: r["speaker"] for r in rows if r["valid"]}
    def find(x):
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x
    hashes = {}
    for r in rows:
        if not r["valid"]:
            continue
        for key in ("pcm_hash", "feature_hash"):
            h = (key, r[key])
            if h in hashes:
                a, b = find(r["speaker"]), find(hashes[h])
                parents[max(a, b)] = min(a, b)
            else:
                hashes[h] = r["speaker"]
    seen = {}
    for r in rows:
        r["split"] = "excluded"
        if not r["valid"]:
            continue
        group = find(r["speaker"])
        fraction = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) / 2**32
        r["split"] = "train" if fraction < .8 else "validation" if fraction < .9 else "test"
        h = r["feature_hash"]
        if h in seen:
            previous = seen[h]
            r["decision"] = "duplicate_removed"
            r["split"] = "excluded"
            if r["label"] != previous["label"]:
                previous["split"] = "excluded"
                previous["decision"] = "conflicting_labels_removed"
                r["decision"] = "conflicting_labels_removed"
        else:
            seen[h] = r
    # Si hubo más de dos copias con etiquetas distintas, excluye todo el grupo.
    conflicts = {r["feature_hash"] for r in rows if r.get("decision") == "conflicting_labels_removed"}
    for r in rows:
        if r.get("feature_hash") in conflicts:
            r["split"], r["decision"] = "excluded", "conflicting_labels_removed"
    return rows

def prepare(cfg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root = Path(cfg["data_dir"])
    paths = sorted(p for p in root.rglob("*.wav") if p.parent.name in cfg["classes"])
    if not paths:
        raise RuntimeError("No hay WAV. Ejecuta primero download o revisa data_dir")
    rows, examples = [], {}
    for path in paths:
        row = dict(path=str(path), label=path.parent.name, speaker="", valid=False,
                   duration=0, channels=0, sample_rate=0, pcm_hash="", feature_hash="", decision="")
        try:
            row["speaker"] = speaker_id(path)
            audio, rate = read_audio(path)
            x = waveform(audio, rate, cfg)
            feature = spectrum(x, cfg)
            row.update(valid=True, duration=len(audio)/rate, channels=audio.shape[1], sample_rate=rate,
                       pcm_hash=hashlib.sha256(audio.tobytes() + str(rate).encode()).hexdigest(),
                       feature_hash=hashlib.sha256(x.tobytes()).hexdigest(),
                       decision="center_crop" if len(audio)/rate > cfg["samples"]/cfg["sample_rate"] else "right_pad_or_keep")
            examples.setdefault(row["label"], (x, feature))
        except Exception as error:
            row["decision"] = f"invalid: {error}"
        rows.append(row)
    rows = assign_splits(rows, cfg["seed"])
    # Validación estricta de cobertura y ausencia de fugas.
    for split in ("train", "validation", "test"):
        labels = {r["label"] for r in rows if r["split"] == split}
        if labels != set(cfg["classes"]):
            raise ValueError(f"Faltan clases en {split}: {set(cfg['classes'])-labels}")
    for field in ("speaker", "pcm_hash", "feature_hash"):
        groups = [{r[field] for r in rows if r["split"] == s} for s in ("train", "validation", "test")]
        assert not any(groups[a] & groups[b] for a, b in ((0,1),(0,2),(1,2)))
    Path("data/metadata").mkdir(parents=True, exist_ok=True)
    with open("data/metadata/inventory.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    write_json("data/metadata/partitions.json", {"config": cfg, "rows": rows})
    speaker_counts = Counter((r["speaker"], r["label"], r["split"]) for r in rows if r["valid"])
    with open("data/metadata/speakers.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["speaker", "class", "split", "files"])
        writer.writerows((*key, count) for key, count in sorted(speaker_counts.items()))

    summary = {"files": len(rows), "valid": sum(r["valid"] for r in rows),
               "speakers": len({r["speaker"] for r in rows if r["valid"]}),
               "original_classes": dict(Counter(r["label"] for r in rows)),
               "decisions": dict(Counter(r["decision"] for r in rows)),
               "splits": {s: dict(Counter(r["label"] for r in rows if r["split"]==s)) for s in ("train","validation","test","excluded")},
               "rates": dict(Counter(r["sample_rate"] for r in rows)),
               "channels": dict(Counter(r["channels"] for r in rows)),
               "duration_min": min(r["duration"] for r in rows if r["valid"]),
               "duration_max": max(r["duration"] for r in rows if r["valid"])}
    write_json("results/dataset_summary.json", summary)
    out = Path("results/figures"); out.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1,2,figsize=(11,4))
    counts = summary["original_classes"]
    ax[0].bar(counts.keys(), counts.values()); ax[0].set_title("Archivos por clase (originales)")
    ax[1].hist([r["duration"] for r in rows if r["valid"]], bins=25); ax[1].set_xlabel("Duración (s)")
    fig.tight_layout(); fig.savefig(out/"dataset.png"); plt.close(fig)
    fig, axes = plt.subplots(len(examples),2,figsize=(10,18))
    for (label,(x,sp)), axis in zip(sorted(examples.items()), axes):
        axis[0].plot(np.arange(len(x))/cfg["sample_rate"],x); axis[0].set_title(label)
        axis[1].imshow(sp[...,0].T, origin="lower",aspect="auto"); axis[1].set_title("log(1 + |STFT|)")
    fig.tight_layout(); fig.savefig(out/"audio_examples.png"); plt.close(fig)
    print(summary)
