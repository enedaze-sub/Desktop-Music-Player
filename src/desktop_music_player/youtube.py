"""On-demand YouTube discovery. Signed stream URLs remain in memory only."""
import sys,re,shutil,time
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import yt_dlp
from .core import Track,youtube_input,playlist_id
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
    results=[]
    for entry in entries or []:
        if not entry or entry.get('is_live') or entry.get('title') in {'[Deleted video]','[Private video]'}:continue
        video_id=entry.get('id','')
        if not re.fullmatch('[A-Za-z0-9_-]{11}',video_id):continue
        results.append(Track(entry.get('title') or '제목 없음','https://www.youtube.com/watch?v='+video_id,'youtube',
                             entry.get('channel') or entry.get('uploader') or '',info.get('title','') if pid else '',entry.get('duration') or 0))
    return results

def resolve(track,video=False,fallback=False):
    youtube_input(track.uri)
    opts=options();opts.update({'noplaylist':True,'format':'bestaudio[ext=webm]/bestaudio/best' if fallback else 'bestaudio[ext=m4a]/bestaudio/best'})
    with yt_dlp.YoutubeDL(opts) as ydl:info=ydl.extract_info(track.uri,download=False)
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
    return {'video_url':video_url,'video_fallback_url':alternate['url'] if alternate else None,
            'url':info['url'],'title':info.get('title') or track.title,'duration':info.get('duration') or 0,
            'has_video':bool(video_url),'expires_at':min(expires) if expires else None,
            'audio_format':str(info.get('format_id') or '')}
