import os,sys,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import Qt,QTimer,QPoint
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
from desktop_music_player.background_editor import BackgroundEditor
from desktop_music_player.settings_editor import SettingsEditor
class EditingRegressionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.w=Window(Store(self.temp.name),demo=True);self.w.show();QTest.qWait(30)
 def tearDown(self):self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(30);self.temp.cleanup()
 def test_zoom_and_drag_do_not_reapply_list_styles_or_whole_theme(self):
  w=self.w;e=BackgroundEditor(w);file=Path(self.temp.name)/'background.png';image=QImage(800,600,QImage.Format_RGB32);image.fill(QColor('red'));image.save(str(file));e.draft['background']=str(file);e.view.setCurrentIndex(1);e.mode.setCurrentIndex(2);e.render_preview()
  original_key=w.surface.cached_background.cacheKey()
  with patch.object(w.drawer,'setStyleSheet') as main_style,patch.object(e.preview_window.drawer,'setStyleSheet') as preview_style:
   for i in range(10):e.zoom.setValue(100+i);e.move_image(.004,0);e.render_preview()
   main_style.assert_not_called();preview_style.assert_not_called();self.assertEqual(w.surface.cached_background.cacheKey(),original_key)
  e.reject();e.deleteLater()
 def test_continuous_input_keeps_rendering_latest_draft_before_release(self):
  e=BackgroundEditor(self.w);e.show();QTest.qWait(50);count=[];e.timer.timeout.connect(lambda:count.append(e.zoom.value()))
  for i in range(55):e.zoom.setValue(100+i);QTest.qWait(5)
  self.assertGreater(len(count),3);QTest.qWait(60);self.assertEqual(count[-1],154);e.reject();e.deleteLater()
 def test_window_opacity_updates_without_reapplying_theme_styles(self):
  d=SettingsEditor(self.w);d.apply_preview()
  with patch.object(self.w,'setStyleSheet') as root,patch.object(self.w.lcd,'setStyleSheet') as lcd,patch.object(self.w.drawer,'setStyleSheet') as drawer:
   for value in range(10,30):d.opacity.setValue(value);d.apply_preview()
   root.assert_not_called();lcd.assert_not_called();drawer.assert_not_called()
  self.assertAlmostEqual(self.w.windowOpacity(),.71,delta=.005);d.reject();d.deleteLater()
 def test_mouse_click_outline_is_hidden_and_tab_focus_remains_visible(self):
  w=self.w;w.activateWindow();w.play.setFocus();QTest.qWait(10);w.pin.setFocus(Qt.TabFocusReason);QTest.qWait(20);self.assertTrue(w.pin.property('keyboardFocus'))
  QTest.mouseClick(w.pin,Qt.LeftButton);QTest.qWait(40);self.assertFalse(w.pin.property('keyboardFocus'))
  self.assertEqual(w.pin.focusPolicy(),Qt.StrongFocus)
 def test_large_batched_library_can_select_last_track_after_scaling(self):
  w=self.w;tracks=[Track(f'Track {i:05d}',f'{i}.mp3') for i in range(12926)];w.set_library(tracks);w.expand('보관함');w.finish_transition();w.set_ui_scale(1.1,persist=False);QTest.qWait(150)
  last=w.library_model.index(len(tracks)-1,0);w.library_view.setCurrentIndex(last);w.library_view.scrollTo(last);QTest.qWait(100)
  self.assertEqual(w.library_view.currentIndex().data(Qt.UserRole),tracks[-1]);rect=w.library_view.visualRect(last)
  self.assertTrue(w.library_view.viewport().rect().intersects(rect));QTest.mouseClick(w.library_view.viewport(),Qt.LeftButton,pos=rect.center());self.assertEqual(w.library_view.selectedIndexes()[0].row(),len(tracks)-1)
  w.search_box.setText('12925');QTest.qWait(350);self.assertEqual(w.library_model.rowCount(),1);self.assertEqual(w.library_model.index(0,0).data(Qt.UserRole),tracks[-1])
