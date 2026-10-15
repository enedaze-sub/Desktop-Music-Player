"""Validate a supplied local test video; it is never copied into the distribution."""
import os,sys,json
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtMultimedia import QMediaPlayer
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts';OUT.mkdir(exist_ok=True);file=Path(sys.argv[1] if len(sys.argv)>1 else OUT/'local-video-test.mp4').resolve();assert file.is_file()
app=QApplication([]);app.setQuitOnLastWindowClosed(False);configure_fonts();w=Window(Store(OUT/'local-video-state'),demo=True);w.show();w.engine.audio.setMuted(True);track=Track('Local video test',str(file));w.set_library([track]);w.engine.play_track(track);QTest.qWait(700)
report={'audio_only_position_ms':w.engine.player.position(),'video_decoder_inactive_when_collapsed':w.engine.video_player is None};assert report['audio_only_position_ms']>150;assert report['video_decoder_inactive_when_collapsed']
w.engine.player.pause();w.engine.seek_to(1800);QTest.qWait(70);source=w.engine.player.source();position=w.engine.player.position();w.expand('영상');w.finish_transition();QTest.qWait(900)
report.update(frame_while_audio_paused=not w.video_widget.image.isNull(),paused_position_preserved=abs(w.engine.player.position()-position)<80,audio_source_unchanged=w.engine.player.source()==source,companion_muted=w.engine.video_audio.isMuted(),primary_video_track_disabled=w.engine.player.activeVideoTrack()==-1)
assert report['frame_while_audio_paused'];assert report['paused_position_preserved'];assert report['audio_source_unchanged'];assert report['companion_muted'];assert report['primary_video_track_disabled']
w.engine.toggle();QTest.qWait(550);assert w.engine.player.position()>position+200;w.grab().save(str(OUT/'local-video.png'));w.expand('영상');w.finish_transition();QTest.qWait(100)
report['close_preserves_audio_and_releases_video']=w.engine.player.source()==source and w.engine.playing() and w.engine.video_player.source().isEmpty();assert report['close_preserves_audio_and_releases_video'];report['passed']=True
(OUT/'local-video-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report);w.engine.stop();w.hide();w.deleteLater();QTest.qWait(50)
