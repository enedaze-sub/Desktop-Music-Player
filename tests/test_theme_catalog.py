"""Built-in gradient themes and lossless upgrade from seeded saved profiles."""
import os,sys,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,load_themes
from desktop_music_player.storage import Store
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.theme_library import legacy_bundled_profiles,profile_from_theme,migrate_bundled_themes
from desktop_music_player.palettes import resolve_theme,lcd_fill,COLOR_LABELS

class ThemeCatalogTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.themes=load_themes()
 def tearDown(self):self.tmp.cleanup()
 def legacy_config(self,index=0):
  p=deepcopy(legacy_bundled_profiles()[index]);cfg=self.store.config();cfg.update(theme='custom',custom_theme_name=p['name'],custom_theme=p['colors'],custom_gradients=p['gradients'],visualizer=p['visualizer']['enabled'],visualizer_style=p['visualizer']['style'],theme_library={q['name']:deepcopy(q) for q in legacy_bundled_profiles()});return cfg
 def test_six_builtins_and_separate_custom_with_unchanged_originals(self):
  self.assertEqual([t['id'] for t in self.themes],['silver_blue','midnight','warm_cream','visualizer','sunset_apricot','lavender_aurora','custom'])
  self.assertEqual(self.store.config()['theme_library'],{})
  self.assertEqual([t['bg'] for t in self.themes[:4]],['#DDE3EC','#0E1320','#EFE6D6','#07090D'])
 def test_light_apricot_contrast_and_aurora_palette_preserved(self):
  def lum(color):
   c=[int(color[i:i+2],16)/255 for i in (1,3,5)];return sum((v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4)*w for v,w in zip(c,(.2126,.7152,.0722)))
  def contrast(a,b):
   x,y=sorted((lum(a),lum(b)));return (y+.05)/(x+.05)
  sun=self.themes[4];aurora=self.themes[5];old=legacy_bundled_profiles()[1]
  self.assertGreater(lum(sun['bg']),.8);self.assertGreater(lum(sun['bg_end']),.7)
  for key in ('bg','panel'):
   for bg in (sun[key],sun[key+'_end']):
    self.assertGreaterEqual(contrast(sun['text'],bg),4.5);self.assertGreaterEqual(contrast(sun['muted'],bg),4.5)
  for bg in (sun['accent'],sun['accent_end']):self.assertGreaterEqual(contrast(sun['on_accent'],bg),4.5)
  self.assertEqual({k:aurora[k] for k in COLOR_LABELS},old['colors']);self.assertEqual(profile_from_theme(aurora)['gradients'],old['gradients'])
 def test_builtin_gradients_ignore_custom_draft_and_use_correct_brush_direction(self):
  cfg=self.store.config();cfg.update(theme='sunset_apricot',custom_gradients={'bg':{'enabled':True,'end':'#010203','direction':'horizontal'}});sun=resolve_theme(cfg,self.themes)
  self.assertEqual(sun['bg_end'],'#FFE3CC');self.assertEqual(sun['bg_direction'],'vertical');self.assertIn('#FFEEDD',lcd_fill(sun));self.assertIn('x2:0,y2:1',lcd_fill(sun))
  cfg['theme']='lavender_aurora';self.assertEqual(resolve_theme(cfg,self.themes)['bg_direction'],'diagonal')
 def test_untouched_active_seed_promotes_and_read_does_not_rewrite_data(self):
  for index,id in enumerate(('sunset_apricot','lavender_aurora')):
   cfg=self.legacy_config(index);self.store.set_many(cfg);before=self.store.db.read_bytes();new=self.store.config()
   self.assertEqual(new['theme'],id);self.assertEqual(new['custom_theme_name'],'');self.assertEqual(new['theme_library'],{});self.assertEqual(self.store.db.read_bytes(),before);self.assertEqual(migrate_bundled_themes(deepcopy(new)),new)
 def test_edited_saved_profiles_and_renamed_copies_are_preserved(self):
  cfg=self.legacy_config();name=cfg['custom_theme_name'];cfg['theme_library'][name]['colors']['bg']='#123456';copy=deepcopy(cfg['theme_library'][name]);copy['name']='내 살구 복사본';cfg['theme_library'][copy['name']]=copy
  new=migrate_bundled_themes(cfg);self.assertEqual(new['theme'],'custom');self.assertEqual(new['theme_library'][name]['colors']['bg'],'#123456');self.assertEqual(new['theme_library'][copy['name']],copy)
 def test_unsaved_color_or_visual_edits_are_kept_as_custom(self):
  for field in ('color','visual'):
   cfg=self.legacy_config();name=cfg['custom_theme_name']
   if field=='color':cfg['custom_theme']['bg']='#123456'
   else:cfg['visualizer_style']='line'
   new=migrate_bundled_themes(cfg);self.assertEqual(new['theme'],'custom');self.assertIn(name,new['theme_library'])
   self.assertEqual(new['theme_library'][name]['colors'],new['custom_theme']);self.assertEqual(new['theme_library'][name]['visualizer']['style'],new['visualizer_style'])
 def test_builtin_live_preview_copy_to_custom_persist_and_cancel(self):
  w=Window(self.store,demo=True);w.show();d=SettingsEditor(w);d.show();original=deepcopy(w.config)
  try:
   with patch.object(w.engine.player,'setSource') as source,patch.object(w.engine.player,'stop') as stop:
    for id,style in (('sunset_apricot','bars'),('lavender_aurora','glow')):
     d.themes.setCurrentIndex(d.themes.findData('base:'+id));d.apply_preview();self.assertEqual(w.theme['id'],id);self.assertEqual(d.preview.theme,w.theme);self.assertFalse(d.custom_panel.isVisible());self.assertEqual(d.visual_style.currentData(),style)
    d.themes.setCurrentIndex(d.themes.findData('base:custom'));d.seed_theme.setCurrentIndex(4);d.copy_preset();d.apply_preview();self.assertTrue(d.custom_panel.isVisible());self.assertEqual(w.theme['bg_end'],'#FFE3CC');self.assertEqual(w.theme['spectrum_end'],'#E0663F');d.reject();self.assertEqual(w.config,original);source.assert_not_called();stop.assert_not_called()
   d.deleteLater();d=SettingsEditor(w);d.themes.setCurrentIndex(d.themes.findData('base:sunset_apricot'));d.accept();self.assertEqual(self.store.config()['theme'],'sunset_apricot');self.assertEqual(self.store.config()['theme_library'],{})
  finally:
   if not d.closed:d.reject()
   d.deleteLater();w.engine.stop();w.hide();w.deleteLater();QTest.qWait(30)
