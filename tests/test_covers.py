import os,sys,tempfile,unittest,wave,threading,time
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QBuffer,QIODevice,QThread
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QTest
from mutagen.wave import WAVE
from mutagen.id3 import APIC
from desktop_music_player.covers import load_cover,decode_image,thumbnail_url,CoverCache,folder_images
from desktop_music_player.core import Track
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
class CoverTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);folder_images.cache_clear()
 def tearDown(self):self.temp.cleanup()
 def image_bytes(self,color):
  image=QImage(300,180,QImage.Format_RGB32);image.fill(QColor(color));buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG');return bytes(buffer.data())
 def test_embedded_cover_precedes_folder_cover(self):
  file=self.root/'song.wav'
  with wave.open(str(file),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(8000);out.writeframes(bytes(1600))
  media=WAVE(file);media.add_tags();media.tags.add(APIC(mime='image/png',type=3,data=self.image_bytes('blue')));media.save();(self.root/'cover.png').write_bytes(self.image_bytes('red'))
  image=load_cover(Track('Song',str(file)));self.assertEqual(image.pixelColor(128,128),QColor('blue'));self.assertEqual(image.size().width(),256)
 def test_folder_cover_is_case_insensitive_and_preferred(self):
  (self.root/'another.png').write_bytes(self.image_bytes('blue'));(self.root/'Cover.PNG').write_bytes(self.image_bytes('red'));image=load_cover(Track('Song',str(self.root/'song.mp3')));self.assertEqual(image.pixelColor(128,128),QColor('red'))
 def test_missing_or_corrupt_images_use_existing_disc(self):
  (self.root/'cover.jpg').write_bytes(b'not an image');track=Track('No cover',str(self.root/'song.mp3'));self.assertTrue(load_cover(track).isNull());cache=CoverCache(enabled=False);self.assertEqual(cache.get(track).cacheKey(),cache.default.cacheKey());self.assertFalse(cache.default.isNull());cache.deleteLater()
 def test_thumbnail_uses_video_id_and_decodes_square(self):
  track=Track('YouTube','https://www.youtube.com/watch?v=dQw4w9WgXcQ','youtube');self.assertEqual(thumbnail_url(track),'https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg');self.assertIsNone(thumbnail_url(Track('Bad','invalid','youtube')))
  response=__import__('unittest.mock',fromlist=['Mock']).Mock();response.url=thumbnail_url(track);response.read.return_value=self.image_bytes('green')
  with patch('desktop_music_player.covers.urlopen') as request:
   request.return_value.__enter__.return_value=response;image=load_cover(track);self.assertEqual(image.pixelColor(128,128),QColor('green'));self.assertEqual(image.width(),image.height())
 def test_art_loading_runs_off_gui_and_negative_results_are_cached(self):
  cache=CoverCache();track=Track('Song','no-cover.mp3');threads=[]
  def load(_):threads.append(QThread.currentThread());return QImage()
  with patch('desktop_music_player.covers.load_cover',side_effect=load) as loader:
   for _ in range(20):cache.get(track)
   for _ in range(40):
    if track.key in cache.cache:break
    time.sleep(.01);self.app.processEvents()
   self.assertIn(track.key,cache.cache);self.assertEqual(cache.get(track).cacheKey(),cache.default.cacheKey());loader.assert_called_once();self.assertIsNot(threads[0],self.app.thread())
  cache.stop();cache.pool.waitForDone(1000);cache.deleteLater();QTest.qWait(20)
 def test_late_cover_never_replaces_current_track_art(self):
  w=Window(Store(self.root/'state'),demo=True);old=Track('Old','old.mp3');current=Track('Current','current.mp3');w.engine.track=current
  red=QImage(256,256,QImage.Format_RGB32);red.fill(QColor('red'));blue=QImage(256,256,QImage.Format_RGB32);blue.fill(QColor('blue'))
  from PySide6.QtGui import QPixmap
  w.covers.cache[current.key]=QPixmap.fromImage(blue);w.refresh_cover();key=w.art.pixmap.cacheKey();w.covers.cache[old.key]=QPixmap.fromImage(red);w.cover_changed(old.key);self.assertEqual(w.art.pixmap.cacheKey(),key)
  w.engine.stop();w.hide();w.deleteLater();QTest.qWait(30)
