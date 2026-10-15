import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import Qt,QModelIndex,QPoint
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtTest import QTest
from desktop_music_player.core import Track,Queue
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
class QueueEditingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.w=Window(Store(self.temp.name),demo=True);self.w.show();self.tracks=[Track(str(i),str(i)) for i in range(6)];self.w.queue.replace(self.tracks);self.w.queue.select(1);self.w.queue.select(2);self.w.engine.track=self.tracks[2];self.w.refresh_queue();QTest.qWait(20)
 def tearDown(self):self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(20);self.temp.cleanup()
 def test_queue_mime_move_preserves_current_history_and_next_song(self):
  w=self.w;model=w.queue_model;mime=model.mimeData([model.index(5,0),model.index(4,0)]);source=w.engine.player.source()
  self.assertTrue(model.dropMimeData(mime,Qt.MoveAction,3,0,QModelIndex()));self.assertEqual([t.title for t in w.queue.tracks],['0','1','2','4','5','3']);self.assertIs(w.queue.current,self.tracks[2]);self.assertEqual(w.engine.player.source(),source);self.assertEqual(w.queue.next(),self.tracks[4]);self.assertEqual(w.queue.previous(),self.tracks[2]);self.assertEqual(w.queue.previous(),self.tracks[1])
 def test_move_current_and_duplicate_rows_keep_correct_playing_occurrence(self):
  w=self.w;w.queue.replace([self.tracks[0],self.tracks[0],self.tracks[2],self.tracks[3]]);w.queue.select(2);w.refresh_queue();w.move_queue([0],4);self.assertIs(w.queue.current,self.tracks[2]);self.assertEqual(w.queue.index,1);self.assertEqual([i.row() for i in w.queue_view.selectedIndexes()],[3]);w.move_queue([1],0);self.assertIs(w.queue.current,self.tracks[2]);self.assertEqual(w.queue.index,0)
 def test_manual_order_disables_shuffle_and_statuses_follow_playback(self):
  w=self.w;w.queue.set_shuffle(True);w.move_queue([5],3);self.assertFalse(w.queue.shuffle);self.assertFalse(w.store.config()['shuffle'])
  roles=[w.queue_model.index(i,0).data(Qt.UserRole+1) for i in range(6)];self.assertEqual(roles,['이전곡','이전곡','현재곡','다음곡','예약 2','예약 3'])
 def test_stale_and_foreign_drag_are_rejected(self):
  w=self.w;m=w.queue_model;mime=m.mimeData([m.index(0,0)]);w.refresh_queue();self.assertFalse(m.dropMimeData(mime,Qt.MoveAction,4,0,QModelIndex()));self.assertEqual(w.queue.tracks,self.tracks)
 def test_context_menu_preserves_multiselection_and_saves_to_existing_playlist(self):
  w=self.w;w.set_library(self.tracks);w.expand('보관함');w.finish_transition();QTest.qWait(25);view=w.library_view
  from PySide6.QtCore import QItemSelectionModel
  for row in (1,2):view.selectionModel().select(w.library_model.index(row,0),QItemSelectionModel.Select)
  w.store.save_playlist('Friends',[self.tracks[0]]);seen=[]
  def choose(menu,pos):
   seen.extend(a.text() for a in menu.actions());sub=next(a.menu() for a in menu.actions() if a.text()=='재생목록에 추가');next(a for a in sub.actions() if a.text()=='Friends').trigger()
  w.track_menu(view,view.visualRect(w.library_model.index(1,0)).center(),False);choose(w._track_menu,None);w._track_menu.close()
  self.assertIn('바로 재생',seen);self.assertEqual([t.title for t in w.store.playlist('Friends')],['0','1','2'])
 def test_context_play_uses_captured_track_after_search_changes(self):
  w=self.w;clicked=Track('Chosen','chosen.mp3');w.set_library([clicked]);w.set_library([Track('Other','other.mp3')])
  with patch.object(w.engine,'play_track') as play:w.play_context_track(clicked,False,0);self.assertIs(w.queue.current,clicked);self.assertIs(play.call_args.args[0],clicked)
