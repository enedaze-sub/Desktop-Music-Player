import os,sys,tempfile,unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication,QAbstractSpinBox,QStyle,QStyleOptionFrame
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.background_editor import BackgroundEditor
class AppearanceLayoutTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def test_numeric_text_fits_at_dialog_scales_and_all_themes(self):
  with tempfile.TemporaryDirectory() as temp:
   w=Window(Store(temp),demo=True);w.show();QTest.qWait(25)
   for factor in (.5,.8,1,1.5):
    w.set_ui_scale(factor,persist=False)
    for theme in w.themes:
     w.config['theme']=theme['id'];w.apply_theme()
     for editor in (SettingsEditor,BackgroundEditor):
      d=editor(w);d.show();QTest.qWait(15)
      for spin in d.findChildren(QAbstractSpinBox):
       if spin.window()!=d:continue
       spin.setValue(spin.maximum());spin.ensurePolished();edit=spin.lineEdit();option=QStyleOptionFrame();option.initFrom(edit);contents=edit.style().subElementRect(QStyle.SE_LineEditContents,option,edit);m=edit.textMargins();metrics=edit.fontMetrics()
       for value in (spin.minimum(),spin.maximum()):
        spin.setValue(value);text=spin.text();self.assertGreaterEqual(contents.width()-m.left()-m.right(),metrics.horizontalAdvance(text)+2,(factor,theme['id'],text,contents))
       self.assertGreaterEqual(contents.height()-m.top()-m.bottom(),metrics.height(),(factor,theme['id'],spin.text(),contents))
      d.reject();d.deleteLater();QTest.qWait(15)
   w.engine.stop();w.hide();w.deleteLater();QTest.qWait(25)
