import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
class AudioRecoveryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.w=Window(Store(self.temp.name),demo=True);self.e=self.w.engine;self.e.track=Track('YouTube','https://youtu.be/dQw4w9WgXcQ','youtube');self.e.last_position=58000;self.e.last_duration=90000
 def tearDown(self):self.e.stop();self.w.hide();self.w.deleteLater();QTest.qWait(20);self.temp.cleanup()
 def test_error_flood_logs_once_and_terminal_failure_stops_decoder(self):
  e=self.e
  with patch.object(e.player,'error',return_value=QMediaPlayer.ResourceError),patch('desktop_music_player.engine.log.warning') as log:
   for _ in range(100):e.error(QMediaPlayer.ResourceError,'Demuxing failed')
   self.assertEqual(log.call_count,1);self.assertEqual(e.retry_count,1);self.assertTrue(e.retry_pending)
   e.retry_timer.stop();e.retry_pending=False;e.retry_count=3;e.recover_audio()
   for _ in range(100):e.error(QMediaPlayer.ResourceError,'Demuxing failed')
   self.assertEqual(log.call_count,1);self.assertTrue(e.failed);self.assertFalse(e.health_timer.isActive());self.assertTrue(e.player.source().isEmpty());self.assertEqual(e.playback_position(),58000)
 def test_pause_during_reconnect_stays_paused_and_restores_position(self):
  e=self.e;e.recover_audio();e.toggle();self.assertFalse(e.autoplay);e.retry_timer.stop();e.retry_pending=False
  with patch.object(e.player,'setSource'),patch.object(e.player,'pause') as pause,patch.object(e.player,'play') as play,patch.object(e.player,'duration',return_value=90000),patch.object(e.player,'setPosition') as seek:
   e.apply_audio({'title':'Song','audio_path':str(Path(self.temp.name)/'cache.m4a'),'duration':90});e.status(QMediaPlayer.LoadedMedia);pause.assert_called_once();play.assert_not_called();seek.assert_called_with(58000);self.assertEqual(e.seek,0)
 def test_watchdog_ignores_pause_and_detects_silent_stall_once(self):
  e=self.e;e.last_progress_at=time.monotonic()-20;e.autoplay=False
  with patch.object(e.player,'position',return_value=58000):
   e.check_audio_health();self.assertEqual(e.retry_count,0);e.autoplay=True;e.check_audio_health();self.assertEqual(e.retry_count,1);e.check_audio_health();self.assertEqual(e.retry_count,1)
 def test_progress_and_healthy_playback_reset_incident_budget(self):
  e=self.e;e.last_progress_at=time.monotonic()-20
  with patch.object(e.player,'position',return_value=59000):e.check_audio_health();self.assertEqual(e.last_position,59000);self.assertEqual(e.retry_count,0)
  e.retry_count=2;e.stable_since=time.monotonic()-31
  with patch.object(e.player,'position',return_value=59000):e.check_audio_health();self.assertEqual(e.retry_count,0)
 def test_stop_and_track_change_cancel_scheduled_recovery(self):
  e=self.e;e.recover_audio();old=e.cancelled;e.stop();self.assertTrue(old.is_set());self.assertFalse(e.retry_timer.isActive());self.assertFalse(e.health_timer.isActive());self.assertFalse(e.failed)
  e.track=Track('Old','https://youtu.be/dQw4w9WgXcQ','youtube');e.recover_audio();old=e.cancelled
  with patch.object(e,'request_audio') as request:e.play_track(Track('New','https://youtu.be/00000000001','youtube'));request.assert_called_once()
  self.assertTrue(old.is_set());self.assertFalse(e.retry_timer.isActive());self.assertEqual(e.retry_count,0)
 def test_cached_audio_fetches_video_only_on_demand(self):
  e=self.e;file=Path(self.temp.name)/'audio.m4a';file.write_bytes(b'cache');e.cache_stream({'title':'Song','audio_path':str(file),'video_url':None})
  with patch.object(e,'submit_stream') as submit,patch.object(e.player,'setSource') as source:
   self.w.show();self.w.expand('영상');self.w.finish_transition();submit.assert_called_once_with('video');source.assert_not_called()
 def test_seek_while_reconnecting_keeps_new_requested_position(self):
  e=self.e;e.recover_audio();e.seek_to(45000);self.assertEqual(e.seek,45000);self.assertEqual(e.playback_position(),45000);self.assertEqual(e.playback_duration(),90000)

 def test_video_lookup_keeps_local_audio_in_memory_cache(self):
  e=self.e;file=Path(self.temp.name)/'audio.m4a';file.write_bytes(b'cache');audio={'title':'Song','audio_path':str(file),'url':None};e.current_stream=audio;e.cache_stream(audio);e.video=True;e.jobs[8]=(None,e.request,'video',e.video_request)
  with patch.object(e,'load_video') as load:
   e.resolved(8,{'title':'Song','url':'https://example.test/remote-audio','video_url':'https://example.test/video'},'');load.assert_called_once();self.assertEqual(e.cached_stream()['audio_path'],str(file));self.assertIsNone(e.cached_stream()['url'])

 def test_end_of_queue_stops_watchdog_and_manual_restart_rearms_it(self):
  e=self.e;e.health_timer.start();e.status(QMediaPlayer.EndOfMedia);self.assertFalse(e.health_timer.isActive())
  with patch.object(e.player,'play') as play:e.toggle();play.assert_called_once();self.assertTrue(e.health_timer.isActive());self.assertLess(time.monotonic()-e.last_progress_at,1)
