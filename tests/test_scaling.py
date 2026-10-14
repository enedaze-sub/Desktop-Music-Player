import os,sys,tempfile,unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QSize,QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
from unittest.mock import patch
class ScaleTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def test_default_repeated_live_scaling_keeps_audio_and_proportions(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Window(Store(folder),demo=True);w.show();QTest.qWait(50)
   self.assertEqual(w.ui_scale,.8);self.assertEqual(w.width(),480);self.assertEqual(w.height(),202)
   with patch.object(w.engine.player,'setSource') as source,patch.object(w.engine.player,'stop') as stop:
    for scale in (.5,1.5,.8,1,.8):
     w.set_ui_scale(scale);QTest.qWait(30)
     self.assertEqual(w.art.width(),round(132*scale));self.assertEqual(w.play.iconSize(),QSize(round(24*scale),round(24*scale)))
     self.assertEqual(w.deck.height(),round(136*scale));self.assertEqual(w.title.font().pixelSize(),round(14*scale))
     self.assertTrue(w.header.rect().contains(w.controls.geometry()))
     w.resize(w.minimumWidth(),w.height());QTest.qWait(30)
     for name,b in w.nav_buttons.items():
      self.assertLessEqual(b.fontMetrics().horizontalAdvance(name)+b.iconSize().width()+round(12*scale),b.width(),(name,scale,b.width()))
     w.expand('영상');w.finish_transition();w.resize(w.minimumWidth(),w.minimumHeight());QTest.qWait(30)
     self.assertTrue(w.video_page.rect().contains(w.video_widget.geometry()))
     self.assertGreaterEqual(w.video_widget.height(),round(120*scale))
     w.expand('영상');w.finish_transition()
    source.assert_not_called();stop.assert_not_called()
   w.hide();w.deleteLater();QTest.qWait(30)
if __name__=='__main__':unittest.main()
