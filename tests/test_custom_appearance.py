import os,sys,tempfile,unittest,math
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import numpy as np
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.palettes import COLOR_LABELS,STYLES,resolve_theme,lcd_colors
from desktop_music_player.widgets import Spectrum
from desktop_music_player.spectrum_analysis import SpectrumAnalyzer
class CustomAppearanceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.w=Window(Store(self.tmp.name),demo=True);self.w.show();QTest.qWait(25)
 def tearDown(self):self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(30);self.tmp.cleanup()
 def editor(self):
  d=SettingsEditor(self.w);d.show();d.themes.setCurrentIndex(next(i for i,t in enumerate(self.w.themes) if t['id']=='custom'));d.visual.setChecked(True);return d
 def test_six_colors_preview_persist_and_cancel_without_interrupting_audio(self):
  w=self.w;original=deepcopy(w.config);saved=w.store.config();d=self.editor()
  colors=dict(zip(COLOR_LABELS,('#211A23','#342635','#FFF4EB','#C7AEBE','#F6AF70','#7E546C')))
  with patch.object(w.engine.player,'setSource') as source,patch.object(w.engine.player,'stop') as stop:
   for key,value in colors.items():self.assertTrue(d.set_color(key,value))
   for style in STYLES:
    d.visual_style.setCurrentIndex(d.visual_style.findData(style));d.apply_preview();self.assertEqual(w.spectrum.style_name,style);self.assertEqual(d.preview.spectrum.style_name,style)
   self.assertTrue(d.custom_panel.isVisible());self.assertEqual(d.preview.theme,w.theme)
   self.assertEqual({k:w.theme[k] for k in COLOR_LABELS},colors);self.assertEqual(lcd_colors(w.theme)[1],colors['panel']);self.assertEqual(w.store.config(),saved)
   d.reject();self.assertEqual(w.config,original);self.assertEqual(w.store.config(),saved);self.assertFalse(d.preview.timer.isActive());source.assert_not_called();stop.assert_not_called()
  d.deleteLater()
  d=self.editor()
  for key,value in colors.items():d.set_color(key,value)
  d.visual_style.setCurrentIndex(d.visual_style.findData('mirror'));d.accept();loaded=w.store.config();self.assertEqual(loaded['custom_theme'],colors);self.assertEqual(loaded['visualizer_style'],'mirror');self.assertEqual(resolve_theme(loaded,w.themes)['accent'],colors['accent']);d.deleteLater()
 def test_presets_copy_and_hex_validation_and_labels(self):
  d=self.editor();d.seed_theme.setCurrentIndex(1);d.copy_preset();self.assertEqual(d.custom_draft,{k:self.w.themes[1][k] for k in COLOR_LABELS})
  for value in ('#123','red','#12345600','x#123456',None):self.assertFalse(d.set_color('accent',value))
  d.color_fields['accent'].setText('#AB1234');d.accept();self.assertEqual(self.w.store.config()['custom_theme']['accent'],'#AB1234')
  texts=[b.text() for b in d.findChildren(QPushButton)];self.assertIn('배경 이미지 꾸미기',texts);self.assertFalse(any('강조색 선택' in t or '꾸미기…' in t for t in texts));self.assertFalse(any('비주얼라이저' in t['name'] for t in self.w.themes));d.deleteLater()
 def test_all_presets_preview_and_mint_visualizer_can_be_disabled(self):
  d=SettingsEditor(self.w);d.show()
  for i,t in enumerate(self.w.themes):
   d.themes.setCurrentIndex(i);d.apply_preview();self.assertEqual(d.preview.theme['id'],t['id']);self.assertFalse(d.preview.grab().isNull())
  d.themes.setCurrentIndex(3);d.visual.setChecked(False);d.apply_preview();self.assertTrue(self.w.spectrum.isHidden());self.assertTrue(d.preview.spectrum.isHidden());d.reject();d.deleteLater()
 def test_visualizer_fits_all_widths_and_scales_without_invasion(self):
  w=self.w;w.config['visualizer']=True
  for factor in (.5,.8,1,1.5):
   w.set_ui_scale(factor,persist=False)
   for width in (560,900,1600):
    w.resize(w.px(width),w.px(252));w.apply_theme();self.app.processEvents();w.lcd.layout().activate()
    self.assertGreaterEqual(w.spectrum.height(),20);self.assertTrue(w.lcd.rect().contains(w.spectrum.geometry()),(factor,width,w.spectrum.geometry(),w.lcd.rect()))
    self.assertLess(w.title.geometry().bottom(),w.time.geometry().top());self.assertLess(w.seek.geometry().bottom(),w.spectrum.geometry().top());self.assertLessEqual(w.spectrum.plot_rect().width(),620*factor+1)
 def test_legacy_mint_setting_migrates_once_and_custom_invalid_colors_fall_back(self):
  store=self.w.store;store.set('theme','visualizer');self.assertTrue(store.config()['visualizer']);store.set_many({'visualizer_style':'bars','visualizer':False});self.assertFalse(store.config()['visualizer'])
  config=dict(self.w.config,theme='custom',custom_theme={'panel':'bad','accent':'#112233','unexpected':'#998877'});t=resolve_theme(config,self.w.themes);self.assertEqual(t['accent'],'#112233');self.assertEqual(t['panel'],self.w.themes[-1]['panel']);self.assertNotIn('unexpected',t)
 def test_four_renderers_are_distinct_and_pause_discards_old_targets(self):
  s=Spectrum();s.resize(510,40);s.show();pixels=[]
  for style in STYLES:
   s.set_style(style);s.levels=[.12+.82*abs(math.sin(i*.3)) for i in range(24)];pixels.append(bytes(s.grab().toImage().constBits()))
  self.assertEqual(len(set(pixels)),4);s.set_active(True);s.accept([1.]*24);s.tick();s.set_active(False);self.assertEqual(s.levels,[0.]*24);self.assertEqual(s.targets,[0.]*24);self.assertFalse(s.timer.isActive());s.hide();s.deleteLater()
class SpectrumAnalysisTests(unittest.TestCase):
 def test_log_bands_detect_bass_and_treble_and_raise_quiet_visible_levels(self):
  rate=48000;t=np.arange(2048)/rate;analyzer=SpectrumAnalyzer()
  low=np.array(analyzer.analyze((.01*np.sin(2*np.pi*110*t)).astype(np.float32),rate));high=np.array(analyzer.analyze((.01*np.sin(2*np.pi*4000*t)).astype(np.float32),rate))
  self.assertEqual(len(low),24);self.assertGreater(low.max(),.5);self.assertGreater(high.max(),.5);self.assertLess(low.argmax(),high.argmax());self.assertEqual(analyzer.analyze(np.zeros(2048),rate),[0.]*24)
 def test_rate_or_size_change_and_noise_are_safe(self):
  analyzer=SpectrumAnalyzer()
  for rate,size in ((44100,1024),(48000,2048),(22050,64)):
   result=analyzer.analyze(np.ones(size,dtype=np.float32)*.00001,rate);self.assertEqual(result,[0.]*24)
  self.assertEqual(analyzer.analyze(np.zeros(32),48000),[0.]*24)
