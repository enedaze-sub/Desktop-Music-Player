import os,sys,json,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.youtube import search,resolve
ROOT=Path(__file__).resolve().parents[1];app=QApplication([]);configure_fonts();w=Window(Store(ROOT/'artifacts'/'video_state'),demo=True);w.engine.audio.setMuted(True);w.show()
results=search('Doul BE ME official');track=results[0]
w.queue.replace([track]);w.queue.select(0)
w.expanded=True;w.tabs.setCurrentIndex(3);w.switch_video(True)
w.engine.play_track(track,video=True)
for _ in range(600):
 time.sleep(.03);app.processEvents();QTest.qWait(100)
 if w.video_widget.videoSink().videoFrame().isValid() and w.engine.player.position()>2000:break
stream={'has_video':bool(w.video_widget.videoSink().videoFrame().isValid())}
report={'has_video_stream':stream['has_video'],'position_ms':w.engine.player.position(),'error':w.engine.player.error().name,'pending_jobs':len(w.engine.jobs),'loading':w.engine.loading,'video_frame_valid':w.video_widget.videoSink().videoFrame().isValid()}
(ROOT/'artifacts'/'video-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
assert report['video_frame_valid'] and report['position_ms']>2000 and report['error']=='NoError',report
w.engine.stop();w.hide();w.deleteLater();QTest.qWait(250)
