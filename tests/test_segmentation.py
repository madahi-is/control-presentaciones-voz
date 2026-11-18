import numpy as np
import pytest
from vozslides.segmentation import Segmenter, noise_threshold

RATE=16000

def block(level):
    return np.full(640,level,dtype=np.float32)

def feed(segmenter, levels):
    return [audio for level in levels if (audio:=segmenter.feed(block(level))) is not None]

def test_silence_and_short_impulse_do_not_trigger():
    s=Segmenter(RATE,.008)
    assert not feed(s,[0]*20+[.1]+[0]*10)

def test_word_and_repeat_after_pause():
    s=Segmenter(RATE,.008)
    outputs=feed(s,[0]*4+[.1]*8+[0]*10+[.1]*8+[0]*10)
    assert len(outputs)==2
    assert all(np.count_nonzero(x)==8*640 for x in outputs)
    assert all(len(x)<=16000 for x in outputs)

def test_continuous_sound_only_once_until_silence():
    s=Segmenter(RATE,.008)
    assert len(feed(s,[.1]*150))==1
    assert not feed(s,[0]*10)
    assert len(feed(s,[.1]*8+[0]*10))==1

def test_noise_calibration_and_reset():
    threshold,noise=noise_threshold([.01]*50,.008)
    assert threshold==pytest.approx(.025) and noise==pytest.approx(.01)
    assert noise_threshold([0]*50,.008)[0]==.008
    for invalid in ([],[float('nan')],[-.1]):
        with pytest.raises(ValueError):noise_threshold(invalid,.008)
    s=Segmenter(RATE,.008)
    feed(s,[.1]*5);s.reset()
    assert not feed(s,[0]*10)


def test_non_action_words_do_not_delay_navigation():
    from vozslides.control import Gate
    gate=Gate(.8,cooldown=1.)
    assert gate.accept(.95,.1,0,consume=False)[0]
    assert gate.accept(.95,.1,.1)[0]
    assert not gate.accept(.95,.1,.2)[0]
