import os,sys,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch,Mock
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,QRectF
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts,COMPACT_HEIGHT
from desktop_music_player.storage import Store
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.palettes import COLOR_LABELS,resolve_theme,gradient_settings
from desktop_music_player.widgets import Surface,Spectrum
from desktop_music_player.core import youtube_input,playlist_id,Track
from desktop_music_player import youtube
class CompactGradientTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.w=Window(Store(self.tmp.name),demo=True);self.w.show();QTest.qWait(20)
 def tearDown(self):self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(25);self.tmp.cleanup()
 def test_top_status_center_and_controls_fit_minimum_at_all_scales(self):
  w=self.w;w.tell('재생 준비 완료 · 긴 상태 설명은 잘라도 창 크기가 바뀌지 않습니다')
  for scale in (.5,.8,1,1.5):
   w.set_ui_scale(scale,persist=False);w.resize(w.px(560),w.px(COMPACT_HEIGHT));self.app.processEvents()
   self.assertIs(w.status_label.parent(),w.bar);self.assertLessEqual(abs(w.status_label.geometry().center().x()-w.bar.rect().center().x()),2)
   self.assertLess(w.brand.geometry().right(),w.status_label.geometry().left());self.assertLess(w.status_label.geometry().right(),w.title_tools.geometry().left());self.assertTrue(w.bar.rect().contains(w.status_label.geometry()))
   bottom=w.controls.mapTo(w,QPoint()).y()+w.controls.height();self.assertGreaterEqual(w.height()-bottom,w.px(6));self.assertLessEqual(w.height()-bottom,w.px(12))
 def test_old_minimum_height_migrates_but_chosen_heights_survive(self):
  s=self.w.store;s.set('compact_height',252);self.assertEqual(s.config()['compact_height'],224)
  s.set('compact_height',320);self.assertEqual(s.config()['compact_height'],320)
  s.set_many({'layout_version':2,'compact_height':252});self.assertEqual(s.config()['compact_height'],252)
 def test_gradient_preview_independent_wave_color_cancel_and_persist(self):
  w=self.w;original=deepcopy(w.config);saved=w.store.config();d=SettingsEditor(w);d.themes.setCurrentIndex(d.themes.findData('base:custom'));d.set_color('accent','#00FF00');d.set_color('spectrum','#BFA0FF');d.visual.setChecked(True)
  with patch.object(w.engine.player,'setSource') as source:
   for key in ('bg','panel','accent','spectrum'):
    d.gradient_checks[key].setChecked(True);self.assertTrue(d.set_gradient_end(key,'#2468AB'));d.gradient_directions[key].setCurrentIndex(d.gradient_directions[key].findData('horizontal'))
   d.apply_preview();self.assertEqual(w.spectrum.color,'#BFA0FF');self.assertEqual(w.spectrum.color_end,'#2468AB');self.assertEqual(w.spectrum.direction,'horizontal');self.assertEqual(d.preview.spectrum.color,w.spectrum.color);self.assertEqual(d.preview.theme,w.theme);self.assertEqual(w.store.config(),saved)
   draft=deepcopy(d.gradient_draft);d.reject();self.assertEqual(w.config,original);self.assertEqual(w.store.config(),saved);source.assert_not_called();d.deleteLater()
  d=SettingsEditor(w);d.themes.setCurrentIndex(d.themes.findData('base:custom'));d.gradient_checks['spectrum'].setChecked(True);d.set_gradient_end('spectrum','#ABCDEF');d.accept();cfg=w.store.config();self.assertEqual(cfg['custom_gradients']['spectrum']['end'],'#ABCDEF');self.assertTrue(cfg['custom_gradients']['spectrum']['enabled']);d.deleteLater()
 def test_actual_surface_and_spectrum_gradients_and_endpoint_cache_invalidation(self):
  colors={k:self.w.themes[-1][k] for k in COLOR_LABELS};colors['bg']='#FF0000';cfg=dict(self.w.config,theme='custom',custom_theme=colors,custom_gradients={'bg':{'enabled':True,'end':'#0000FF','direction':'horizontal'}});t=resolve_theme(cfg,self.w.themes)
  surface=Surface();surface.resize(320,100);surface.set_theme(t);surface.show();image=surface.grab().toImage();self.assertGreater(image.pixelColor(10,50).red(),200);self.assertGreater(image.pixelColor(310,50).blue(),200);first=surface.cached_background.cacheKey()
  t['bg_end']='#00FF00';surface.set_theme(t);image=surface.grab().toImage();self.assertNotEqual(surface.cached_background.cacheKey(),first);self.assertGreater(image.pixelColor(310,50).green(),200);surface.hide();surface.deleteLater()
  spectrum=Spectrum();spectrum.resize(300,40);spectrum.set_colors('#FF0000','#0000FF','horizontal');spectrum.levels=[1.]*24;spectrum.show();image=spectrum.grab().toImage();self.assertGreater(image.pixelColor(6,20).red(),200);self.assertGreater(image.pixelColor(294,20).blue(),200);spectrum.hide();spectrum.deleteLater()
 def test_invalid_gradient_data_and_preset_copy_reset_are_safe(self):
  colors={k:self.w.themes[-1][k] for k in COLOR_LABELS};r=gradient_settings({'bg':{'enabled':'true','end':'bad','direction':'bad'},'panel':42},colors);self.assertFalse(r['bg']['enabled']);self.assertEqual(r['bg']['end'],colors['bg']);self.assertEqual(r['bg']['direction'],'vertical')
  d=SettingsEditor(self.w);d.themes.setCurrentIndex(d.themes.findData('base:custom'));d.gradient_checks['spectrum'].setChecked(True);d.gradient_directions['spectrum'].setCurrentIndex(2);d.copy_preset();self.assertFalse(d.gradient_checks['spectrum'].isChecked());self.assertEqual(d.gradient_directions['spectrum'].currentData(),'vertical');self.assertFalse(d.set_gradient_end('bg','#123'));d.reject();d.deleteLater()
class PlaylistLinkTests(unittest.TestCase):
 def test_shared_formatted_and_protocol_less_links_normalize(self):
  base='https://youtube.com/playlist?list=PLexample&si=tracking'
  for value in (base,'<'+base+'>','['+base+']('+base+')',base.removeprefix('https://'),base.replace('&','\\&')):
   self.assertEqual(playlist_id(value),'PLexample');self.assertTrue(youtube_input(value).startswith('https://'))
  with self.assertRaises(ValueError):youtube_input('https://youtube.com.evil.test/playlist?list=PLexample')
 def test_full_playlist_is_not_capped_and_keeps_original_order_and_duplicates(self):
  fake=Mock();entries=[{'id':f'{i:011d}','title':str(i)} for i in range(337)];entries.append(entries[0]);fake.extract_info.return_value={'title':'Example','entries':iter(entries)}
  with patch.object(youtube.yt_dlp,'YoutubeDL') as factory:
   factory.return_value.__enter__.return_value=fake;session=youtube.SearchSession('https://youtube.com/playlist?list=PLexample&si=tracking');result=session.get_page(0);self.assertEqual(len(result['tracks']),338);self.assertEqual([t.title for t in result['tracks']],[str(i) for i in range(337)]+['0']);self.assertNotIn('playlistend',factory.call_args.args[0]);self.assertFalse(result['has_more']);session.close()
  fake.extract_info.assert_called_once_with('https://www.youtube.com/playlist?list=PLexample',download=False,process=False)
class PlaylistUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def test_pasting_playlist_in_local_search_switches_and_adds_all(self):
  with tempfile.TemporaryDirectory() as state:
   w=Window(Store(state),demo=True);calls=[];tracks=[Track(str(i),f'https://www.youtube.com/watch?v={i:011d}','youtube') for i in range(25)]
   with patch.object(w,'submit',side_effect=lambda fn,args,callback,**kw:calls.append(callback)):
    w.search_box.setText('https://youtube.com/playlist?list=PLexample&si=tracking');w.search();self.assertEqual(w.source,'youtube');self.assertFalse(w.add_all_button.isEnabled());calls[-1]({'tracks':tracks,'page':0,'has_more':False},'');self.assertIn('재생목록 전체 추가 (25곡)',w.add_all_button.text());w.add_all_button.click();self.assertEqual(w.queue.tracks,tracks);self.assertIsNone(w.engine.track)
   w.youtube_session.close();w.engine.stop();w.hide();w.deleteLater();QTest.qWait(30)
