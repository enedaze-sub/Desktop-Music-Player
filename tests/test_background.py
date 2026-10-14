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
 def test_surface_original_color_tint_and_transparency(self):
  surface=Surface();surface.resize(200,120);surface.set_theme({'bg':'#26374a','border':'#26374a'});values={**BACKGROUND_DEFAULTS,'background':str(self.image),'background_opacity':1,'background_tint':0};surface.configure_background(values);surface.show();QTest.qWait(20)
  def center():return surface.grab().toImage().pixelColor(100,60)
  self.assertEqual(center().name(),'#e53b28');values['background_tint']=1;surface.configure_background(values);self.assertEqual(center().name(),'#26374a');values['background_tint']=0;values['background_opacity']=0;surface.configure_background(values);self.assertNotEqual(center().name(),'#e53b28');surface.hide();surface.deleteLater()
if __name__=='__main__':unittest.main()
