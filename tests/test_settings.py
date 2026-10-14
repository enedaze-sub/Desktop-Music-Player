import os,sys,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.background_editor import BackgroundEditor
class SettingsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.w=Window(Store(self.temp.name),demo=True);self.w.show();QTest.qWait(30)
 def tearDown(self):self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(30);self.temp.cleanup()
 def test_live_theme_opacity_scale_and_cancel_without_writing_or_moving_slider(self):
  w=self.w;original=deepcopy(w.config);saved=w.store.config();size=w.size();d=SettingsEditor(w);d.show();QTest.qWait(40);slider_size=d.scale.slider.size();dialog_size=d.size()
  self.assertEqual((d.scale.slider.minimum(),d.scale.slider.maximum()),(50,150))
  with patch.object(w.engine.player,'setSource') as source,patch.object(w.engine.player,'stop') as stop:
   d.themes.setCurrentIndex(1);d.opacity.slider.setValue(25);d.scale.slider.setValue(125);QTest.qWait(120)
   self.assertEqual(w.theme['id'],w.themes[1]['id']);self.assertAlmostEqual(w.windowOpacity(),.75,delta=.005);self.assertEqual(w.ui_scale,1.25)
   self.assertEqual(d.scale.slider.size(),slider_size);self.assertEqual(d.size(),dialog_size);self.assertEqual(w.store.config(),saved)
   d.reject();QTest.qWait(50);self.assertEqual(w.config,original);self.assertEqual(w.size(),size);self.assertEqual(w.store.config(),saved);source.assert_not_called();stop.assert_not_called()
  d.deleteLater()
 def test_apply_commits_theme_opacity_and_scale_together(self):
  w=self.w;d=SettingsEditor(w);d.themes.setCurrentIndex(2);d.opacity.slider.setValue(15);d.scale.slider.setValue(70);d.accept();saved=w.store.config()
  self.assertEqual(saved['theme'],w.themes[2]['id']);self.assertEqual(saved['opacity'],.85);self.assertEqual(saved['ui_scale'],.7);d.deleteLater()
 def test_nested_background_apply_then_outer_cancel_rolls_back(self):
  w=self.w;before=deepcopy(w.config);d=SettingsEditor(w);e=BackgroundEditor(w,persist=False,parent=d);e.draft['background_list_transparency']=.7;e.accept();self.assertEqual(w.config['background_list_transparency'],.7)
  self.assertEqual(w.store.config()['background_list_transparency'],0);d.reject();self.assertEqual(w.config,before);e.deleteLater();d.deleteLater()

 def test_escape_and_window_close_restore_the_live_draft(self):
  w=self.w;before=deepcopy(w.config)
  for action in ('escape','close'):
   d=SettingsEditor(w);d.show();d.activateWindow();d.themes.setCurrentIndex(1);d.opacity.setValue(30);QTest.qWait(90)
   if action=='escape':QTest.keyClick(d,Qt.Key_Escape)
   else:d.close()
   QTest.qWait(40);self.assertEqual(w.config,before);self.assertEqual(w.store.config()['opacity'],before['opacity']);d.deleteLater();QTest.qWait(30)
