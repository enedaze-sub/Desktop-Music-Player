"""Real network playback regression: pane switches, seek, pause and raster video."""
import os,sys,json,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.youtube import search
ROOT=Path(__file__).resolve().parents[1];app=QApplication([]);configure_fonts();w=Window(Store(ROOT/'artifacts'/'video_state'),demo=True);w.engine.audio.setMuted(True);w.show()
def wait_for(predicate,seconds=50):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  time.sleep(.02);app.processEvents()
  if predicate():return
 raise AssertionError('Timed out; audio='+w.engine.player.error().name+' video='+(w.engine.video_player.error().name if w.engine.video_player else 'not opened'))
report=[]
for query in ('Doul BE ME official','Ar Tonelico III EXEC_COSMOFLIPS lyrics'):
 tracks=search(query);assert tracks;track=tracks[0];w.queue.replace([track]);w.queue.select(0)
 w.engine.play_track(track);wait_for(lambda:w.engine.player.position()>2000 and not w.engine.loading)
 source=w.engine.player.source();position=w.engine.player.position()
 w.expand('영상');w.finish_transition();wait_for(lambda:not w.video_widget.image.isNull() and w.engine.video_player.position()>500)
 assert w.engine.player.source()==source and w.engine.player.position()>=position
 w.engine.seek_to(15000);wait_for(lambda:w.engine.player.position()>15000);QTest.qWait(1200)
 assert abs(w.engine.video_player.position()-w.engine.player.position())<1000
 w.engine.toggle();QTest.qWait(250);paused=w.engine.player.position()
 w.expand('영상');w.finish_transition();QTest.qWait(150)
 w.expand('영상');w.finish_transition();wait_for(lambda:not w.video_widget.image.isNull())
 QTest.qWait(800);assert abs(w.engine.player.position()-paused)<250 and not w.engine.playing()
 w.resize(w.minimumWidth(),w.minimumHeight());QTest.qWait(200)
 assert w.video_page.rect().contains(w.video_widget.geometry())
 w.hide();QTest.qWait(200);assert not w.engine.video_player.isPlaying();w.show();wait_for(lambda:not w.video_widget.image.isNull())
 item={'query':query,'title':track.title,'audio_error':w.engine.player.error().name,'video_error':w.engine.video_player.error().name,'audio_source_unchanged':w.engine.player.source()==source,'rendered_frame':not w.video_widget.image.isNull(),'paused_position_preserved':abs(w.engine.player.position()-paused)<250,'minimum_video_contained':True}
 report.append(item);w.grab().save(str(ROOT/'artifacts'/('video-rendered-'+str(len(report))+'.png')))
 assert item['audio_error']=='NoError' and item['video_error']=='NoError',item
 w.expand('영상');w.finish_transition();w.engine.stop()
(ROOT/'artifacts'/'video-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True))
w.hide();w.deleteLater();QTest.qWait(250)
