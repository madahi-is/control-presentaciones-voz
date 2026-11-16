import copy
import numpy as np
import pytest
from vozslides.audio import waveform,features
from vozslides.common import config
from vozslides.control import Navigation,Gate,ACTIONS
from vozslides.prepare import speaker_id,assign_splits

def test_audio_shared_processing():
    cfg=config(); t=np.arange(8000)/8000
    stereo=np.stack([np.sin(2*np.pi*440*t)]*2,axis=1).astype(np.float32)
    x=waveform(stereo,8000,cfg)
    assert x.shape==(16000,)
    sp=features(stereo,8000,cfg)
    assert sp.shape==(98,257,1) and np.isfinite(sp).all()
    np.testing.assert_allclose(sp,features(x,16000,cfg),atol=1e-6)
    assert np.argmax(sp.mean(axis=0)[:,0]) in (14,)
    assert waveform(np.ones(100),16000,cfg)[-1]==0
    assert waveform(np.arange(20000,dtype=np.float32),16000,cfg)[0]==2000
    with pytest.raises(ValueError):waveform(np.array([np.nan]),16000,cfg)

def test_speakers_duplicates():
    assert speaker_id("right/abc123_nohash_2.wav")=="abc123"
    with pytest.raises(ValueError):speaker_id("anon.wav")
    rows=[dict(speaker=s,label=l,valid=True,pcm_hash=h,feature_hash=h,decision="ok") for s,l,h in
          [("a","go","same"),("b","go","same"),("a","left","other"),("b","right","third"),("c","yes","fourth")]]
    result=assign_splits(copy.deepcopy(rows),42)
    assert result[1]["split"]=="excluded"
    assert result[0]["split"]==result[2]["split"]==result[3]["split"]
    for field in ("speaker","feature_hash"):
        sets=[{r[field] for r in result if r["split"]==s} for s in ("train","validation","test")]
        assert not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
    conflict=copy.deepcopy(rows);conflict[1]["label"]="stop"
    result=assign_splits(conflict,42)
    assert result[0]["split"]==result[1]["split"]=="excluded"

def test_navigation_and_map():
    nav=Navigation()
    assert not nav.apply("start")
    nav.pages=3
    for _ in range(10):nav.apply("next")
    assert nav.index==2
    nav.apply("start");assert nav.index==0 and nav.presenting
    nav.apply("next");nav.apply("finish")
    assert nav.pages==3 and nav.index==1 and not nav.presenting
    for _ in range(10):nav.apply("previous")
    assert nav.index==0
    assert ACTIONS=={"right":"next","left":"previous","go":"start","stop":"finish"}
    assert all(word not in ACTIONS for word in ("yes","no","up","down"))

def test_rejection_and_cooldown():
    gate=Gate(.8)
    assert not gate.accept(.99,0,0)[0]
    assert not gate.accept(.7,.1,0)[0]
    assert gate.accept(.9,.1,0)[0]
    assert not gate.accept(.9,.1,.5)[0]
    assert gate.accept(.9,.1,1.1)[0]


def test_spanish_requires_actual_spanish_labels():
    from vozslides.control import command_action
    english=config()["classes"]
    assert command_action("siguiente",english) is None
    assert command_action("right",english)=="next"
    assert command_action("siguiente",["anterior","finalizar","iniciar","siguiente"])=="next"
    assert command_action("yes",english) is None
