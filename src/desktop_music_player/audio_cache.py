"""Bounded compressed-audio cache; no transcoding or signed URLs on disk."""
import json,os,re,time,uuid
from pathlib import Path
from threading import Lock
MAX_FILE=48*1024*1024
MAX_TOTAL=192*1024*1024
MAX_TRACKS=12
MAX_AGE=24*3600
LOCK=Lock()
class CacheTooLarge(ValueError):pass

def cached_audio(folder,track):
    folder=Path(folder).resolve();manifest=folder/(track.key+'.json')
    try:
        if time.time()-manifest.stat().st_mtime>MAX_AGE:return None
        meta=json.loads(manifest.read_text(encoding='utf-8'));name=meta['filename']
        if Path(name).name!=name or not name.startswith(track.key+'.') or Path(name).suffix not in {'.m4a','.webm','.mp4','.opus','.ogg'}:return None
        file=folder/name
        if not file.is_file() or file.stat().st_size!=meta['size'] or not 0<meta['size']<=MAX_FILE:return None
        os.utime(file,None);os.utime(manifest,None)
        return {'audio_path':str(file),'url':None,'title':meta['title'],'duration':meta['duration'],'audio_format':meta['audio_format'],'video_url':None,'video_fallback_url':None,'expires_at':None}
    except (OSError,ValueError,KeyError,TypeError):return None

def prune(folder,keep=None):
    folder=Path(folder).resolve();keep=set(keep or ())
    if not folder.exists():return
    with LOCK:
        groups={}
        for file in folder.iterdir():
            if file.parent!=folder or not file.is_file() or not re.fullmatch(r'[0-9a-f]{24}\..+',file.name):continue
            key=file.name[:24];groups.setdefault(key,[]).append(file)
        entries=[]
        for key,files in groups.items():
            try:entries.append((max(p.stat().st_mtime for p in files),key,sum(p.stat().st_size for p in files),files))
            except OSError:continue
        total=sum(e[2] for e in entries);count=len(entries)
        for modified,key,size,files in sorted(entries):
            if key in keep:continue
            if total<=MAX_TOTAL and count<=MAX_TRACKS and time.time()-modified<=MAX_AGE:continue
            for file in files:
                try:file.unlink()
                except OSError:pass  # Windows may still have the previous source open.
            total-=size;count-=1

def invalidate(folder,track):
    folder=Path(folder).resolve()
    if not folder.exists():return
    for file in folder.glob(track.key+'.*'):
        if file.parent==folder and file.is_file():
            try:file.unlink()
            except OSError:pass

def prepare(ydl,info,result,folder,track,cancelled=None):
    if cancelled is not None and cancelled.is_set():raise ValueError('재생 요청이 취소되었습니다.')
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True);prune(folder,{track.key})
    size=info.get('filesize') or info.get('filesize_approx') or 0
    if info.get('is_live') or info.get('live_status') in {'is_live','is_upcoming'} or size>MAX_FILE or (info.get('duration') or 0)>1800:return result
    started=time.monotonic()
    def progress(data):
        if cancelled is not None and cancelled.is_set():raise ValueError('재생 요청이 취소되었습니다.')
        if data.get('downloaded_bytes',0)>MAX_FILE:raise CacheTooLarge('오디오 캐시 크기 제한')
        if time.monotonic()-started>90:raise ValueError('오디오 준비 시간이 초과되었습니다.')
    stem=track.key+'.'+uuid.uuid4().hex[:8]
    ydl.params.update(outtmpl={'default':str(folder/(stem+'.%(ext)s'))},http_chunk_size=1024*1024,retries=2,fragment_retries=2,concurrent_fragment_downloads=1,nopart=False)
    ydl.add_progress_hook(progress)
    def cleanup():
        for partial in folder.glob(stem+'.*'):
            if partial.parent==folder and partial.is_file():
                try:partial.unlink()
                except OSError:pass
    try:ydl.process_info(info)
    except Exception as error:
        cleanup()
        if isinstance(error,CacheTooLarge):return result
        raise
    if cancelled is not None and cancelled.is_set():
        cleanup();raise ValueError('재생 요청이 취소되었습니다.')
    file=Path(ydl.prepare_filename(info)).resolve()
    if file.parent!=folder or not file.name.startswith(track.key+'.') or not file.is_file():raise ValueError('오디오 준비 파일을 확인하지 못했습니다.')
    size=file.stat().st_size
    if not 0<size<=MAX_FILE:invalidate(folder,track);return result
    meta={'filename':file.name,'size':size,'title':result['title'],'duration':result['duration'],'audio_format':result['audio_format']}
    temporary=folder/(track.key+'.json.tmp');temporary.write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8');temporary.replace(folder/(track.key+'.json'));prune(folder,{track.key})
    return {**result,'audio_path':str(file),'url':None}
