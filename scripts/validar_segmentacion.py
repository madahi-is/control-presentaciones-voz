"""Replay de WAV de validación: verifica el recorrido, no mide un micrófono real."""
import argparse
import time
import numpy as np
from vozslides.common import read_json,write_json
from vozslides.audio import read_audio,waveform
from vozslides.segmentation import Segmenter
from vozslides.inference import Predictor

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--min-voice-ms',type=int,choices=[40,80,120],default=80)
args=parser.parse_args()
p=Predictor()
meta=read_json('data/metadata/partitions.json')
if meta['config']!=p.cfg:raise ValueError('El modelo y las particiones usan distinta configuración')
rows=[r for r in meta['rows'] if r['split']=='validation']
counts={'files':len(rows),'detected':0,'correct':0,'above_threshold':0,'above_threshold_correct':0,'minimum_voice_ms':args.min_voice_ms,'no_segment':0,'multiple_segments':0}
start=time.monotonic()
for row in rows:
    audio,rate=read_audio(row['path'])
    x=waveform(audio,rate,p.cfg)
    # Mismo WAV, con silencio anterior/posterior; sin ruido añadido.
    block=int(p.cfg['sample_rate']*.04)
    stream=np.pad(x,(block*5,block*10))
    segmenter=Segmenter(p.cfg['sample_rate'],p.cfg['silence_rms'],p.cfg['release_ms'],min_voice_ms=args.min_voice_ms)
    segments=[]
    for i in range(0,len(stream)-block+1,block):
        segment=segmenter.feed(stream[i:i+block])
        if segment is not None:segments.append(segment)
    if len(segments)!=1:
        counts['no_segment' if not segments else 'multiple_segments']+=1
        continue
    counts['detected']+=1
    word,confidence=p.predict(segments[0],p.cfg['sample_rate'])
    correct=word==row['label'];counts['correct']+=int(correct)
    if confidence>=p.info['threshold']:
        counts['above_threshold']+=1;counts['above_threshold_correct']+=int(correct)
counts['accuracy_including_missed']=counts['correct']/len(rows)
counts['seconds']=time.monotonic()-start
counts['confidence_counts_scope']='Solo umbral softmax; no mide gate energético ni espera entre pronunciaciones'
counts['scope']='WAV de validación con silencio sintético; sin micrófono, sin calibración de ruido y sin ajuste de parámetros según prueba'
write_json('results/segmentation_validation'+('' if args.min_voice_ms==80 else '_'+str(args.min_voice_ms)+'ms')+'.json',counts)
print(counts)
