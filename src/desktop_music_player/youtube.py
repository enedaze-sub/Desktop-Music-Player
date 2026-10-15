"""On-demand YouTube discovery. Signed stream URLs remain in memory only."""
import sys,re,shutil,time
from threading import Lock,Event
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import yt_dlp
from .core import Track,youtube_input,playlist_id
from . import audio_cache
class Quiet:
    def debug(self,m):pass
    def warning(self,m):pass
    def error(self,m):pass

def options():
    base=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))
    candidates=[base/'tools'/'deno.exe',Path(sys.executable).parent/'deno.exe']
    deno=next((str(p) for p in candidates if p.is_file()),None) or shutil.which('deno')
    return {'quiet':True,'no_warnings':True,'logger':Quiet(),'socket_timeout':15,'retries':1,'extractor_retries':1,'cachedir':False,
            'js_runtimes':{'deno':{'path':deno}} if deno else {}}

def search(value):
    query=youtube_input(value); pid=playlist_id(value)
    opts=options();opts.update({'extract_flat':True,'noplaylist':not bool(pid),'playlistend':300})
    if pid:query='https://www.youtube.com/playlist?list='+pid
    with yt_dlp.YoutubeDL(opts) as ydl:info=ydl.extract_info(query,download=False)
    if not info:return []
    entries=info.get('entries') if 'entries' in info else [info]
    return [track for entry in entries or [] if (track:=entry_track(entry,info.get('title','') if pid else ''))]

def entry_track(entry,album=''):
    if not entry or entry.get('is_live') or entry.get('title') in {'[Deleted video]','[Private video]'}:return None
    video_id=entry.get('id','')
    if not re.fullmatch('[A-Za-z0-9_-]{11}',video_id):return None
    return Track(entry.get('title') or '제목 없음','https://www.youtube.com/watch?v='+video_id,'youtube',entry.get('channel') or entry.get('uploader') or '',album,entry.get('duration') or 0)

class SearchSession:
    """Consume YouTube continuation lazily; keep visited pages in memory only."""
    PAGE_SIZE=10
    def __init__(self,value):
        self.query=youtube_input(value);self.value=value.strip();self.paged=self.query.startswith('ytsearch10:')
        self._lock=Lock();self._cancelled=Event();self._iterator=None;self._tracks=[];self._seen=set();self._exhausted=False
    def _iter_tracks(self):
        opts=options();opts.update(extract_flat=True,lazy_playlist=True,noplaylist=True)
        with yt_dlp.YoutubeDL(opts) as ydl:
            # lazy_playlist still processes every entry before extract_info returns.
            # Keep the extractor's raw iterator so only this page + one lookahead
            # is consumed; continuation requests happen on the next page.
            info=ydl.extract_info('ytsearchall:'+self.query.split(':',1)[1],download=False,process=False)
            for entry in (info or {}).get('entries') or []:
                if self._cancelled.is_set():return
                track=entry_track(entry)
                if track:yield track
    def _close_iterator(self):
        if self._iterator is not None:
            self._iterator.close();self._iterator=None
    def close(self):
        self._cancelled.set()
        # Never wait for an in-flight network request on the GUI thread.
        if self._lock.acquire(blocking=False):
            try:self._close_iterator()
            finally:self._lock.release()
    def get_page(self,page):
        if page<0:raise ValueError('페이지 번호를 확인해 주세요.')
        with self._lock:
            try:
                if self._cancelled.is_set():raise ValueError('취소된 검색입니다.')
                if not self.paged:
                    if not self._exhausted:self._tracks=search(self.value);self._exhausted=True
                    return {'tracks':list(self._tracks),'page':0,'has_more':False}
                end=(page+1)*self.PAGE_SIZE
                while len(self._tracks)<=end and not self._exhausted:
                    if self._cancelled.is_set():raise ValueError('취소된 검색입니다.')
                    if self._iterator is None:self._iterator=self._iter_tracks()
                    try:track=next(self._iterator)
                    except StopIteration:self._exhausted=True;self._close_iterator();break
                    except Exception:
                        self._close_iterator();raise
                    if track.key not in self._seen:self._tracks.append(track);self._seen.add(track.key)
                return {'tracks':self._tracks[page*self.PAGE_SIZE:end],'page':page,'has_more':len(self._tracks)>end}
            finally:
                if self._cancelled.is_set():self._close_iterator()

def resolve(track,video=False,fallback=False,cache_folder=None,cancelled=None):
    youtube_input(track.uri)
    if cancelled is not None and cancelled.is_set():raise ValueError('재생 요청이 취소되었습니다.')
    if cache_folder is not None and not video:
        if fallback:audio_cache.invalidate(cache_folder,track)
        cached=audio_cache.cached_audio(cache_folder,track)
        if cached:return cached
    opts=options();opts.update({'noplaylist':True,'format':'bestaudio[ext=webm]/bestaudio/best' if fallback else 'bestaudio[ext=m4a]/bestaudio/best'})
    with yt_dlp.YoutubeDL(opts) as ydl:return _resolved_info(ydl,ydl.extract_info(track.uri,download=False),track,video,cache_folder,cancelled)

def _resolved_info(ydl,info,track,video,cache_folder,cancelled):
    if not info or not info.get('url'):raise ValueError('재생 가능한 스트림을 찾지 못했습니다.')
    candidates=[f for f in info.get('formats',[]) if f.get('vcodec','none')!='none' and f.get('url') and 0<(f.get('height') or 0)<=720 and (f.get('fps') or 30)<=30 and f.get('protocol','').startswith(('http','m3u8'))]
    candidates.sort(key=lambda f:(str(f.get('vcodec','')).startswith(('avc','h264')),f.get('height') or 0,f.get('acodec','none')=='none',-(f.get('tbr') or 0)),reverse=True)
    first=candidates[0] if candidates else None
    smaller=[f for f in candidates[1:] if (f.get('height') or 0)<=480 and f.get('url')!=first['url']] if first else []
    alternate=smaller[0] if smaller else candidates[1] if len(candidates)>1 else None
    video_url=first['url'] if first else info['url'] if info.get('vcodec','none')!='none' else None
    urls=[info['url']]+([video_url] if video_url else [])
    expires=[]
    for url in urls:
        value=parse_qs(urlparse(url).query).get('expire',[])
        if value:
            try:expires.append(float(value[0]))
            except ValueError:expires.append(time.time())
    result={'video_url':video_url,'video_fallback_url':alternate['url'] if alternate else None,
            'url':info['url'],'title':info.get('title') or track.title,'duration':info.get('duration') or 0,
            'has_video':bool(video_url),'expires_at':min(expires) if expires else None,
            'audio_format':str(info.get('format_id') or '')}

    if cache_folder is not None and not video:return audio_cache.prepare(ydl,info,result,cache_folder,track,cancelled)
    return result
