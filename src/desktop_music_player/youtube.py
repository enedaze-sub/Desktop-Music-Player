"""On-demand YouTube discovery. Signed stream URLs remain in memory only."""
import sys,re,shutil
from pathlib import Path
import yt_dlp
from .core import Track,youtube_input,playlist_id
class Quiet:
    def debug(self,m):pass
    def warning(self,m):pass
    def error(self,m):pass

def options():
    deno=shutil.which('deno')
    if not deno:
        base=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))
        for candidate in [Path(sys.executable).parent/'deno.exe',base/'tools'/'deno.exe',base/'deno.exe']:
            if candidate.exists():deno=str(candidate);break
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

def resolve(track,video=False):
    youtube_input(track.uri)
    opts=options();opts.update({'noplaylist':True,'format':'bestaudio/best'})
    with yt_dlp.YoutubeDL(opts) as ydl:info=ydl.extract_info(track.uri,download=False)
    if not info or not info.get('url'):raise ValueError('재생 가능한 스트림을 찾지 못했습니다.')
    candidates=[f for f in info.get('formats',[]) if f.get('vcodec','none')!='none' and f.get('url') and 0<(f.get('height') or 0)<=720 and f.get('protocol','').startswith(('http','m3u8'))]
    preferred=[f for f in candidates if str(f.get('vcodec','')).startswith(('avc','h264'))] or candidates
    selected=max(preferred,key=lambda f:(f.get('height') or 0,1 if (f.get('fps') or 30)<=30 else 0,-(f.get('tbr') or 0))) if preferred else None
    video_url=selected['url'] if selected else info['url'] if info.get('vcodec','none')!='none' else None
    return {'video_url':video_url,'url':info['url'],'title':info.get('title') or track.title,'duration':info.get('duration') or 0,
            'has_video':bool(video_url)}
