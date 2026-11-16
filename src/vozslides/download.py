import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path
from .common import write_json

URL = "https://storage.googleapis.com/download.tensorflow.org/data/mini_speech_commands.zip"

def download(manual_zip=None):
    raw = Path("data/raw")
    raw.mkdir(parents=True, exist_ok=True)
    archive = Path(manual_zip) if manual_zip else raw / "mini_speech_commands.zip"
    if not archive.exists():
        if manual_zip:
            raise FileNotFoundError(archive)
        temporary = archive.with_suffix(".part")
        try:
            with urllib.request.urlopen(URL, timeout=90) as source, temporary.open("wb") as target:
                shutil.copyfileobj(source, target)
            temporary.replace(archive)
        except Exception as error:
            raise RuntimeError("Descarga fallida. Descarga el ZIP manualmente y usa: vozslides download --zip RUTA") from error
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f"ZIP dañado: {bad}")
        for member in z.infolist():
            destination = (raw / member.filename).resolve()
            if not destination.is_relative_to(raw.resolve()):
                raise ValueError("Ruta insegura en ZIP")
            # Solo el dataset; omite metadatos de macOS.
            if member.filename.startswith("mini_speech_commands/") and not destination.exists():
                z.extract(member, raw)
    write_json("data/metadata/download.json", {"url": URL, "sha256": digest, "archive": str(archive)})
    print("Dataset disponible en", raw / "mini_speech_commands")
