import os,sys,json,time,statistics
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track,scan_library
from desktop_music_player.youtube import search,resolve
import psutil
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts';app=QApplication([]);configure_fonts()
window=Window(Store(ART/'perf_state'),demo=True);window.engine.audio.setMuted(True);window.show();QTest.qWait(200)
process=psutil.Process();report={}
def measure(label,seconds=8):
 process.cpu_percent(None);start=time.monotonic();values=[]
 while time.monotonic()-start<seconds:
  QTest.qWait(250);values.append(process.cpu_percent(None))
 report[label]={'cpu_one_core_percent_mean':round(statistics.mean(values),2),'rss_mb':round(process.memory_info().rss/1024**2,1),'sample_seconds':seconds}
measure('idle')
roots=Store().roots();start=time.monotonic();library=scan_library(roots);report['library']={'tracks':len(library),'scan_seconds':round(time.monotonic()-start,2)}
window.set_library(library)
window.engine.player.setLoops(-1);window.engine.play_track(Track('Sample',str(ART/'sample.wav')));QTest.qWait(500);measure('audio_only')
window.config['theme']='visualizer';window.apply_theme();QTest.qWait(500);measure('visualizer_visible')
window.hide();QTest.qWait(200);measure('playing_in_background')
window.engine.stop();print('Local performance complete',flush=True)
try:
 tracks=search('Doul BE ME official');report['youtube_search_results']=len(tracks)
 if not tracks:raise ValueError('No results')
 stream=resolve(tracks[0]);report['youtube_stream_resolved']=True
 window.engine.player.setLoops(1);window.engine.track=tracks[0]
 from PySide6.QtCore import QUrl
 window.engine.player.setSource(QUrl(stream['url']));window.engine.player.play();QTest.qWait(6000)
 report['youtube_playback_position_ms']=window.engine.player.position();report['youtube_media_error']=window.engine.player.error().name
 window.engine.stop()
except Exception as error:
 report['youtube_error_type']=type(error).__name__
(ART/'performance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
