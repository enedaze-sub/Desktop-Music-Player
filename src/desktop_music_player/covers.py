"""Lazy, bounded artwork loading. Workers decode QImages; only GUI creates pixmaps."""
import base64,re,sys,struct
from pathlib import Path
from functools import lru_cache
from collections import OrderedDict
from urllib.parse import urlparse,parse_qs
from urllib.request import Request,urlopen
import mutagen
from PySide6.QtCore import QObject,Signal,Slot,QThreadPool,QBuffer,QByteArray,QIODevice,Qt
from PySide6.QtGui import QImage,QImageReader,QPixmap
from .core import app_root
from .jobs import Job
IMAGE_LIMIT=8*1024*1024
IMAGE_TYPES={'.jpg','.jpeg','.png','.webp','.bmp'}

def decode_image(data):
    if not data or len(data)>IMAGE_LIMIT:return QImage()
    buffer=QBuffer();buffer.setData(QByteArray(data));buffer.open(QIODevice.ReadOnly);reader=QImageReader(buffer);reader.setAutoTransform(True);size=reader.size()
    if not size.isValid() or max(size.width(),size.height())>30000:return QImage()
    if max(size.width(),size.height())>512:reader.setScaledSize(size.scaled(512,512,Qt.KeepAspectRatio))
    image=reader.read()
    if image.isNull():return image
    image=image.scaled(256,256,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
    return image.copy((image.width()-256)//2,(image.height()-256)//2,256,256)

def embedded_images(file):
    try:
        media=mutagen.File(file);tags=media.tags if media else None
        pictures=sorted(getattr(media,'pictures',[]) or [],key=lambda pic:pic.type!=3)
        for picture in pictures:yield picture.data
        if not tags:return
        if hasattr(tags,'getall'):
            for picture in sorted(tags.getall('APIC'),key=lambda pic:pic.type!=3):yield picture.data
        for cover in tags.get('covr',[]):yield bytes(cover)
        for picture in tags.get('WM/Picture',[]):
            data=bytes(picture.value);length=struct.unpack_from('<I',data,1)[0];offset=5
            for _ in range(2):
                while data[offset:offset+2]!=b'\x00\x00' and offset+2<=len(data):offset+=2
                offset+=2
            yield data[offset:offset+length]
        for encoded in tags.get('metadata_block_picture',[]):
            from mutagen.flac import Picture
            yield Picture(base64.b64decode(encoded)).data
        for encoded in tags.get('coverart',[]):yield base64.b64decode(encoded)
    except Exception:return

@lru_cache(maxsize=256)
def folder_images(folder):
    try:
        files=sorted((file for file in Path(folder).iterdir() if file.is_file() and file.suffix.lower() in IMAGE_TYPES),key=lambda file:file.name.casefold())
        preferred={'cover':0,'folder':1,'front':2,'album':3,'albumart':4}
        return tuple(sorted(files,key=lambda file:(preferred.get(file.stem.casefold(),5),file.name.casefold())))
    except OSError:return ()

def thumbnail_url(track):
    parsed=urlparse(track.uri);video_id=parse_qs(parsed.query).get('v',[''])[0]
    if parsed.hostname in ('youtu.be','www.youtu.be'):video_id=parsed.path.strip('/')
    return 'https://i.ytimg.com/vi/'+video_id+'/mqdefault.jpg' if re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id) else None

def load_cover(track):
    if track.kind=='youtube':
        url=thumbnail_url(track)
        if not url:return QImage()
        try:
            with urlopen(Request(url,headers={'User-Agent':'DesktopMusicPlayer/0.1'}),timeout=6) as response:
                if urlparse(response.url).hostname!='i.ytimg.com':return QImage()
                return decode_image(response.read(IMAGE_LIMIT+1))
        except Exception:return QImage()
    file=Path(track.uri)
    for data in embedded_images(str(file)):
        image=decode_image(data)
        if not image.isNull():return image
    for candidate in folder_images(str(file.parent)):
        try:
            if candidate.stat().st_size>IMAGE_LIMIT:continue
            image=decode_image(candidate.read_bytes())
            if not image.isNull():return image
        except OSError:continue
    return QImage()

class CoverCache(QObject):
    changed=Signal(str)
    def __init__(self,parent=None,enabled=True):
        super().__init__(parent);self.enabled=enabled;self.default=QPixmap(str(Path(getattr(sys,'_MEIPASS',app_root()))/'assets/default-cover.png'));self.cache=OrderedDict();self.pending=set();self.jobs={};self.ident=0;self.generation=0
        self.pool=QThreadPool(self);self.pool.setMaxThreadCount(2)
    def get(self,track,priority=0):
        if track is None:return self.default
        key=track.key
        if key in self.cache:self.cache.move_to_end(key);return self.cache[key]
        if self.enabled and key not in self.pending and (priority>0 or len(self.pending)<24):
            self.ident+=1;job=Job(self.ident,load_cover,track);self.pending.add(key);self.jobs[self.ident]=(job,key,self.generation);job.signals.done.connect(self.done);self.pool.start(job,priority)
        return self.default
    @Slot(int,object,str)
    def done(self,ident,image,error):
        entry=self.jobs.pop(ident,None)
        if not entry:return
        _,key,generation=entry
        if generation!=self.generation:return
        self.pending.discard(key);self.cache[key]=QPixmap.fromImage(image) if not error and isinstance(image,QImage) and not image.isNull() else self.default
        while len(self.cache)>96:self.cache.popitem(last=False)
        self.changed.emit(key)
    def invalidate(self):
        self.generation+=1;self.cache.clear();self.pending.clear();folder_images.cache_clear()
    def stop(self):
        self.enabled=False;self.pool.clear()
