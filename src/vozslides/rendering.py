"""Caché acotada: una rasterización grande sirve también para la vista previa."""
from collections import OrderedDict
import time


class PageImages:
    def __init__(self, capacity=4):
        self.capacity = capacity
        self.images = OrderedDict()
        self.variants = OrderedDict()
        self.rasterizations = 0
        self.last_seconds = 0.

    def clear(self):
        self.images.clear()
        self.variants.clear()

    def get(self, page, width, height):
        import pymupdf
        from PIL import Image
        width, height = max(1,int(width)), max(1,int(height))
        scale = min(width/page.rect.width, height/page.rect.height,
                    1920/page.rect.width, 1080/page.rect.height)
        target = (max(1,int(page.rect.width*scale)),max(1,int(page.rect.height*scale)))
        key = (id(page.parent),page.number)
        variant_key=(key,target)
        if variant_key in self.variants:
            self.variants.move_to_end(variant_key)
            return self.variants[variant_key]
        cached = self.images.get(key)
        if cached is None or cached.width < target[0] or cached.height < target[1]:
            start = time.perf_counter()
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
            cached = Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
            self.images[key] = cached
            self.rasterizations += 1
            self.last_seconds = time.perf_counter()-start
        self.images.move_to_end(key)
        while len(self.images)>self.capacity:
            self.images.popitem(last=False)
        result=cached.resize(target,Image.Resampling.BILINEAR) if cached.size!=target else cached
        self.variants[variant_key]=result
        while len(self.variants)>self.capacity*2:
            self.variants.popitem(last=False)
        return result
