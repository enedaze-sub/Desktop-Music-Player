import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QVideoFrame
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts,EXPANDED_BASE,MIN_PANEL_HEIGHT,COMPACT_HEIGHT
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
from desktop_music_player.engine import Engine,safe_error
class UIRegressionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False);configure_fonts()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();store=Store(self.temp.name);store.set("ui_scale",1);self.w=Window(store,demo=True);self.w.show();self.w.activateWindow();QTest.qWait(40)
 def tearDown(self):
  self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(30);self.temp.cleanup()
 def test_drawer_animation_is_monotonic_and_header_never_moves(self):
  w=self.w;art=w.art.mapTo(w,QPoint(0,0));nav=w.nav_rail.mapTo(w,QPoint(0,0));saved=w.saved_height
  for _ in range(2):
   w.expand('보관함');heights=[]
   for _ in range(12):
    QTest.qWait(20);heights.append(w.height());self.assertEqual(w.art.mapTo(w,QPoint(0,0)),art);self.assertEqual(w.nav_rail.mapTo(w,QPoint(0,0)),nav)
   self.assertEqual(heights,sorted(heights));self.assertEqual(w.height(),EXPANDED_BASE+saved)
   w.expand('보관함');heights=[]
   for _ in range(12):QTest.qWait(20);heights.append(w.height());self.assertEqual(w.art.mapTo(w,QPoint(0,0)),art)
   self.assertEqual(heights,sorted(heights,reverse=True));self.assertEqual(w.height(),COMPACT_HEIGHT);self.assertEqual(w.saved_height,saved)
 def test_rapid_reversal_and_minimum_video_size(self):
  w=self.w;w.expand('영상');QTest.qWait(45);w.expand('영상');QTest.qWait(40);w.expand('영상');w.finish_transition()
  w.resize(560,260);self.app.processEvents()
  self.assertGreaterEqual(w.height(),EXPANDED_BASE+MIN_PANEL_HEIGHT)
  self.assertGreaterEqual(w.video_widget.height(),120)
  self.assertTrue(w.video_page.rect().contains(w.video_widget.geometry()))
  self.assertLess(w.nav_rail.mapTo(w,QPoint()).y()+w.nav_rail.height(),w.drawer_viewport.y())
 def test_space_on_button_toggles_once_and_typing_keeps_spaces_and_ctrl_arrows(self):
  w=self.w;w.engine.track=Track('Song','missing.mp3');w.play.setFocus()
  with patch.object(w.engine,'toggle') as toggle:
   QTest.keyClick(w.play,Qt.Key_Space);toggle.assert_called_once()
  w.focus_search();w.search_box.setText('one two');w.search_box.setFocus()
  with patch.object(w.engine,'toggle') as toggle,patch.object(w,'next') as next_track:
   QTest.keyClick(w.search_box,Qt.Key_Space);self.assertEqual(w.search_box.text(),'one two ')
   QTest.keyClick(w.search_box,Qt.Key_Right,Qt.ControlModifier);next_track.assert_not_called();toggle.assert_not_called()
 def test_ctrl_volume_and_queue_keyboard_navigation(self):
  w=self.w;w.expand('대기열');w.finish_transition();w.queue_view.setFocus();start=w.volume.value()
  QTest.keyClick(w.queue_view,Qt.Key_Up,Qt.ControlModifier);self.assertEqual(w.volume.value(),start+5)
  QTest.keyClick(w.queue_view,Qt.Key_Down);self.assertEqual(w.volume.value(),start+5)
 def test_all_edges_and_corners_resize_in_compact_mode(self):
  w=self.w;w.resize(700,340);self.app.processEvents();self.assertEqual(w.compact_height,340)
  self.assertEqual(len(w.resize_handles),8)
  self.assertTrue(all(h.active_edges()==h.edges for h in w.resize_handles))
  self.assertGreater(w.grab().toImage().pixelColor(0,0).alpha(),0)
  w.expand('보관함');w.finish_transition();w.expand('보관함');w.finish_transition();self.assertEqual(w.height(),340)
  w.resize(560,100);self.app.processEvents();self.assertGreaterEqual(w.height(),COMPACT_HEIGHT)
 def test_corner_and_bottom_drag_fallback_changes_both_dimensions(self):
  w=self.w;w.resize(700,340);self.app.processEvents();corner=w.resize_handles[-1]
  with patch.object(w,'windowHandle',return_value=None):
   QTest.mousePress(corner,Qt.LeftButton,pos=QPoint(2,2));QTest.mouseMove(corner,QPoint(-38,-28));QTest.mouseRelease(corner,Qt.LeftButton,pos=QPoint(2,2))
  self.app.processEvents();self.assertEqual(w.size().width(),660);self.assertEqual(w.size().height(),310)
  bottom=w.resize_handles[3]
  with patch.object(w,'windowHandle',return_value=None):
   QTest.mousePress(bottom,Qt.LeftButton,pos=QPoint(100,2));QTest.mouseMove(bottom,QPoint(100,-18));QTest.mouseRelease(bottom,Qt.LeftButton,pos=QPoint(100,2))
  self.app.processEvents();self.assertEqual(w.width(),660);self.assertEqual(w.height(),290);self.assertEqual(w.compact_height,290)
 def test_canvas_paints_real_frame_inside_minimum_geometry(self):
  w=self.w;w.expand('영상');w.finish_transition();image=QImage(160,90,QImage.Format_RGB32);image.fill(QColor('#e33645'))
  w.video_widget.videoSink().setVideoFrame(QVideoFrame(image));QTest.qWait(50)
  self.assertFalse(w.video_widget.image.isNull());grab=w.video_widget.grab().toImage();center=grab.pixelColor(grab.width()//2,grab.height()//2)
  self.assertGreater(center.red(),150);self.assertLess(center.green(),100)
 def test_video_mode_never_replaces_audio_source(self):
  w=self.w;w.engine.track=Track('YouTube','https://youtu.be/dQw4w9WgXcQ','youtube');result={'url':'https://example.test/audio','video_url':'https://example.test/video','title':'Song'};w.engine.cache_stream(result)
  with patch.object(w.engine.player,'setSource') as audio_source,patch.object(w.engine,'load_video') as video:
   w.expand('영상');w.finish_transition();video.assert_called_once_with(result['video_url'])
   w.expand('영상');w.finish_transition();audio_source.assert_not_called()
 def test_recovery_is_bounded_preserves_position_and_discards_bad_cache(self):
  engine=self.w.engine;engine.track=Track('YouTube','https://youtu.be/dQw4w9WgXcQ','youtube');engine.last_position=23000;engine.cache_stream({'url':'https://example.test/expired','title':'Song'})
  with patch.object(engine,'request_audio') as reload:
   engine.recover_audio();self.assertIsNone(engine.cached_stream());self.assertEqual(engine.seek,23000);QTest.qWait(200);reload.assert_called_once()
   engine.recover_audio();QTest.qWait(180);self.assertEqual(reload.call_count,1);self.assertFalse(engine.loading)
 def test_late_worker_result_and_signed_urls_cannot_leak(self):
  engine=self.w.engine;engine.track=Track('Current','https://youtu.be/dQw4w9WgXcQ','youtube');engine.jobs[7]=(None,engine.request-1,'audio',0)
  with patch.object(engine,'apply_audio') as apply:engine.resolved(7,{'title':'Old'},'');apply.assert_not_called()
  text=safe_error('HTTP 403 https://media.test/a?sig=private&ip=1.2.3.4 refused');self.assertNotIn('private',text);self.assertNotIn('1.2.3.4',text)


 def test_local_video_mode_uses_muted_companion_without_audio_source_reset(self):
  w=self.w;w.expand('영상');w.finish_transition();file=Path(self.temp.name)/'clip.mp4';file.touch();track=Track('Video',str(file));w.engine.track=track;w.engine.video=False
  with patch.object(w.engine.player,'setSource') as source,patch.object(w.engine,'load_video') as load,patch.object(w.engine,'submit_stream') as network:
   w.engine.set_video_mode(True,w.video_widget);self.assertEqual(Path(load.call_args.args[0].toLocalFile()).resolve(),file.resolve());source.assert_not_called();network.assert_not_called()
 def test_local_video_error_never_tries_youtube_resolution(self):
  from PySide6.QtMultimedia import QMediaPlayer
  w=self.w;w.expand('영상');w.finish_transition();w.engine.track=Track('Video','clip.mp4');w.engine.video=True;w.engine.video_visible=True
  with patch.object(w.engine,'submit_stream') as network:w.engine.video_error(QMediaPlayer.FormatError,'unsupported');QTest.qWait(180);network.assert_not_called()

if __name__=='__main__':unittest.main()
