"""Comprobaciones de extremo a extremo de audio y artefactos presentes."""
from pathlib import Path
import json
import numpy as np
import pytest
import soundfile as sf
from vozslides.audio import read_audio,features
from vozslides.common import config


def test_file_and_array_same_features(tmp_path):
    cfg=config()
    x=np.sin(2*np.pi*330*np.arange(22050)/22050).astype(np.float32)*.3
    path=tmp_path/'stereo.wav'
    sf.write(path,np.column_stack([x,x]),22050,subtype='FLOAT')
    decoded,rate=read_audio(path)
    np.testing.assert_allclose(features(decoded,rate,cfg),features(x,22050,cfg),atol=1e-6)
    damaged=tmp_path/'broken.wav';damaged.write_bytes(b'not a wav')
    with pytest.raises((RuntimeError,ValueError)):
        read_audio(damaged)


def test_real_partitions_if_available():
    path=Path('data/metadata/partitions.json')
    if not path.exists():pytest.skip('Primero ejecutar prepare')
    meta=json.loads(path.read_text())
    for split in ('train','validation','test'):
        assert {r['label'] for r in meta['rows'] if r['split']==split}==set(meta['config']['classes'])
    for field in ('speaker','pcm_hash','feature_hash'):
        groups=[{r[field] for r in meta['rows'] if r['split']==s} for s in ('train','validation','test')]
        assert not (groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2])


def test_demo_pdf():
    import pymupdf
    path=Path('assets/demo.pdf')
    if not path.exists():pytest.skip('Primero ejecutar demo')
    with pymupdf.open(path) as doc:
        assert len(doc)==4
        assert 'Control de presentaciones' in doc[0].get_text()
        assert doc[0].get_pixmap().width>0
