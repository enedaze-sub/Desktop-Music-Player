import os,sys,tempfile,unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store,BACKGROUND_DEFAULTS
from desktop_music_player.background_editor import BackgroundEditor
from desktop_music_player.widgets import Surface
class BackgroundTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.image=root/'background.png';image=QImage(160,100,QImage.Format_RGB32);image.fill(QColor('#e53b28'));image.save(str(self.image));self.w=Window(Store(root/'state'),demo=True);self.w.show();QTest.qWait(30)
 def tearDown(self):self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(20);self.temp.cleanup()
 def test_preview_drag_and_cancel_do_not_persist_draft(self):
  original=dict(self.w.config);editor=BackgroundEditor(self.w);editor.show();QTest.qWait(30);editor.draft['background']=str(self.image);editor.zoom.setValue(175);editor.original_colors();editor.move_image(.25,-.15);QTest.qWait(50)
  self.assertFalse(editor.preview.pixmap.isNull());self.assertAlmostEqual(editor.draft['background_x'],.25);self.assertEqual(editor.zoom.slider.value(),175)
  editor.reject();self.assertEqual(self.w.config,original);self.assertEqual(self.w.store.config()['background'],'');editor.deleteLater()
 def test_apply_persists_all_transform_fields_and_original_color(self):
  editor=BackgroundEditor(self.w);editor.draft['background']=str(self.image);editor.zoom.setValue(200);editor.x.setValue(20);editor.original_colors();editor.accept();saved=self.w.store.config()
  self.assertEqual(saved['background_zoom'],2);self.assertEqual(saved['background_x'],.2);self.assertEqual(saved['background_opacity'],1);self.assertEqual(saved['background_tint'],0);self.assertEqual(saved['background'],str(self.image));editor.deleteLater()
 def test_expanded_profile_and_preview_never_change_actual_drawer_or_media(self):
  from unittest.mock import patch
  from copy import deepcopy
  w=self.w;state=(w.expanded,w.size(),w.tabs.currentIndex(),deepcopy(w.config));e=BackgroundEditor(w);e.draft['background']=str(self.image);e.sync_controls();e.show()
  with patch.object(w.engine.player,'setSource') as source,patch.object(w.engine.player,'stop') as stop:
   e.view.setCurrentIndex(1);e.mode.setCurrentIndex(2);e.zoom.setValue(220);e.x.setValue(35);e.list_transparency.setValue(65);QTest.qWait(90)
   self.assertEqual(e.draft['background_zoom'],1);self.assertEqual(e.draft['background_expanded']['background_zoom'],2.2);self.assertTrue(e.preview_window.expanded);self.assertGreater(e.preview.pixmap.height(),w.height())
   self.assertEqual((w.expanded,w.size(),w.tabs.currentIndex(),w.config),state);source.assert_not_called();stop.assert_not_called()
   e.view.setCurrentIndex(0);self.assertEqual(e.zoom.value(),100);e.accept()
  saved=w.store.config();self.assertEqual(saved['background_expanded']['background_x'],.35);self.assertEqual(saved['background_list_transparency'],.65);e.deleteLater()
 def test_header_crop_stays_fixed_and_independent_profile_changes_expanded_pixels(self):
  image=QImage(240,360,QImage.Format_RGB32)
  for y in range(360):
   for x in range(240):image.setPixelColor(x,y,QColor(y%255,x%255,90))
  image.save(str(self.image));surface=Surface();surface.resize(240,140);surface.set_theme({'bg':'#26374a','border':'#26374a'})
  values={**BACKGROUND_DEFAULTS,'background':str(self.image),'background_opacity':1,'background_expanded_mode':'header'};surface.configure_background(values);surface.set_background_view(False,140);surface.show();QTest.qWait(20)
  color=surface.grab().toImage().pixelColor(120,70);surface.resize(240,360);surface.set_background_view(True,140);QTest.qWait(20);self.assertEqual(surface.grab().toImage().pixelColor(120,70),color)
  values.update(background_expanded_mode='custom',background_expanded={'background_zoom':2,'background_x':.2});surface.configure_background(values);self.assertNotEqual(surface.grab().toImage().pixelColor(120,70),color);surface.hide();surface.deleteLater()
 def test_surface_original_color_tint_and_transparency(self):
  surface=Surface();surface.resize(200,120);surface.set_theme({'bg':'#26374a','border':'#26374a'});values={**BACKGROUND_DEFAULTS,'background':str(self.image),'background_opacity':1,'background_tint':0};surface.configure_background(values);surface.show();QTest.qWait(20)
  def center():return surface.grab().toImage().pixelColor(100,60)
  self.assertEqual(center().name(),'#e53b28');values['background_tint']=1;surface.configure_background(values);self.assertEqual(center().name(),'#26374a');values['background_tint']=0;values['background_opacity']=0;surface.configure_background(values);self.assertNotEqual(center().name(),'#e53b28');surface.hide();surface.deleteLater()
if __name__=='__main__':unittest.main()
