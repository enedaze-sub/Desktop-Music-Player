"""Portable music library and queue; no Qt or network dependencies."""
from __future__ import annotations
import hashlib, os, random, re, sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse, parse_qs
AUDIO={'.mp3','.flac','.wav','.m4a','.ogg','.opus','.aac','.wma','.aiff'}
VIDEO={'.mp4','.mkv','.webm','.mov'}
def app_root():
    return Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]
@dataclass
class Track:
    title: str
    uri: str
    kind: str='local'
    artist: str=''
    album: str=''
    duration: float=0
    @property
    def key(self):return hashlib.sha256((self.kind+'\0'+self.uri).encode()).hexdigest()[:24]
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):
        if data.get('kind','local') not in {'local','youtube'}:raise ValueError('Unknown track source')
        return cls(**{key:data[key] for key in cls.__dataclass_fields__ if key in data})

def scan_library(roots):
    result=[]; seen=set();visited=set()
    for root in roots:
        pending=[Path(root)]
        while pending:
            folder=pending.pop()
            try:
                real=os.path.normcase(os.path.abspath(folder))
                if real in visited:continue
                visited.add(real)
                with os.scandir(folder) as entries:
                    for entry in entries:
                        if entry.is_symlink():continue
                        if entry.is_dir(follow_symlinks=False):pending.append(Path(entry.path))
                        elif entry.is_file() and Path(entry.name).suffix.lower() in AUDIO:
                            path=Path(os.path.abspath(entry.path)); key=os.path.normcase(str(path))
                            if key in seen:continue
                            seen.add(key)
                            result.append(Track(Path(entry.name).stem,str(path),album=path.parent.name))
            except (OSError,PermissionError):continue
    return sorted(result,key=lambda track:track.title.casefold())

class Queue:
    def __init__(self,tracks=None):
        self.tracks=list(tracks or []);self.index=-1;self.shuffle=False;self.repeat='off';self.history=[];self.bag=[]
    @property
    def current(self):return self.tracks[self.index] if 0<=self.index<len(self.tracks) else None
    def append(self,tracks):
        start=len(self.tracks);self.tracks.extend(tracks);self.bag.extend(range(start,len(self.tracks)))
    def select(self,index):
        if not 0<=index<len(self.tracks):return None
        if self.index>=0 and self.index!=index:self.history.append(self.index)
        self.index=index
        if index in self.bag:self.bag.remove(index)
        return self.current
    def next(self,automatic=False):
        if not self.tracks:return None
        if automatic and self.repeat=='one' and self.current:return self.current
        if self.shuffle:
            available=[n for n in self.bag if n!=self.index]
            if not available:
                if self.repeat=='off' and self.index>=0:return None
                self.bag=list(range(len(self.tracks)));available=[n for n in self.bag if n!=self.index] or self.bag
            return self.select(random.choice(available))
        target=self.index+1
        if target>=len(self.tracks):
            if self.repeat!='all':return None
            target=0
        return self.select(target)
    def previous(self):
        if self.history:
            self.index=self.history.pop();return self.current
        return self.select(max(0,self.index-1))
    def remove(self,index):
        if not 0<=index<len(self.tracks):raise IndexError(index)
        current_removed=index==self.index
        del self.tracks[index]
        if index<=self.index:self.index-=1
        self.history=[n-(n>index) for n in self.history if n!=index]
        self.bag=[n-(n>index) for n in self.bag if n!=index]
        return current_removed
    def set_shuffle(self,value):
        self.shuffle=value;self.bag=[n for n in range(len(self.tracks)) if n!=self.index]
    def replace(self,tracks):
        self.tracks=list(tracks);self.index=-1;self.history=[];self.bag=list(range(len(self.tracks)))

def youtube_input(value):
    value=value.strip()
    if not value or len(value)>500:raise ValueError('검색어나 주소를 500자 이내로 입력해 주세요.')
    parsed=urlparse(value)
    if parsed.scheme or value.startswith('//'):
        if parsed.scheme not in {'https','http'} or (parsed.hostname or '').lower() not in {'youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','www.youtu.be'} or parsed.username or parsed.password:
            raise ValueError('유튜브 주소만 입력할 수 있습니다.')
        return value
    return 'ytsearch10:'+value

def playlist_id(value):
    query=youtube_input(value)
    if query.startswith('ytsearch'):return None
    values=parse_qs(urlparse(query).query)
    return values.get('list',[None])[0]
