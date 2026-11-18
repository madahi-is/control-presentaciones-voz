"""Microbenchmark del PDF demo; no mide el tiempo total de la aplicación."""
import time
import pymupdf
from PIL import Image
from vozslides.common import write_json
from vozslides.rendering import PageImages

with pymupdf.open('assets/demo.pdf') as document:
    # Calienta la lectura del PDF para no atribuir a la caché el coste inicial.
    document[0].get_pixmap()
    sizes=[(1366,768),(700,400)]
    start=time.perf_counter()
    for turn in range(24):
        page=document[turn%len(document)]
        for width,height in sizes:
            scale=min(width/page.rect.width,height/page.rect.height)
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
            Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    original=time.perf_counter()-start
    cache=PageImages()
    start=time.perf_counter()
    for turn in range(24):
        page=document[turn%len(document)]
        for width,height in sizes:cache.get(page,width,height)
    current=time.perf_counter()-start
result={'scope':'24 cambios cíclicos por las 4 páginas de demo.pdf; proyección y vista previa; no incluye Tk, CNN ni audio',
        'previous_rasterizations':48,'cached_rasterizations':cache.rasterizations,
        'previous_seconds':original,'cached_seconds':current}
write_json('results/render_benchmark.json',result)
print(result)
