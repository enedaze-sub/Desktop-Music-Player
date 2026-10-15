"""Replay the reported 90-second sample across the old failure point; muted."""
import os,sys,json,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
from desktop_music_player.youtube import resolve
if len(sys.argv)<2:raise SystemExit('Usage: python tools/smoke_audio_stability.py YOUTUBE_URL (90-second test video)')
ROOT=Path(__file__).resolve().parents[1];app=QApplication([]);app.setQuitOnLastWindowClosed(False);configure_fonts();w=Window(Store(ROOT/'artifacts/stability-state'),demo=True);w.engine.audio_cache_folder=ROOT/'artifacts/stability-audio-cache';track=Track('Stability test',sys.argv[1],'youtube');result=resolve(track,cache_folder=w.engine.audio_cache_folder);assert result.get('audio_path');w.engine.track=track;w.engine.cache_stream(result);w.queue.replace([track]);w.engine.audio.setMuted(True);w.play_index(0)
report={'audio_is_local':False,'max_position_ms':0,'ended':False,'errors':[]};w.engine.player.positionChanged.connect(lambda value:report.update(max_position_ms=max(report['max_position_ms'],value)));w.engine.player.errorOccurred.connect(lambda error,text:report['errors'].append(error.name))
def seek():
 report['audio_is_local']=w.engine.player.source().isLocalFile();w.engine.seek_to(50000)
def finish():
 report['crossed_old_failure_point']=report['max_position_ms']>60000;report['reached_end']=report['ended'];report['retries']=w.engine.retry_count;report['passed']=report['audio_is_local'] and report['crossed_old_failure_point'] and report['reached_end'] and not report['errors'];(ROOT/'artifacts/audio-stability-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report,flush=True);w.engine.stop();w.hide();w.deleteLater();app.quit()
w.engine.ended.connect(lambda:report.update(ended=True));QTimer.singleShot(700,seek);QTimer.singleShot(44000,finish);ticker=QTimer();ticker.setInterval(10000);ticker.timeout.connect(lambda:print('position_ms',w.engine.playback_position(),'error',w.engine.player.error().name,flush=True));ticker.start();app.exec()
