import os,sys,tempfile,unittest,json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.theme_library import *
class ThemeLibraryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);store=Store(self.root/'state');profiles=deepcopy(bundled_profiles())
  for i,p in enumerate(profiles):p['name']='사용자 테마 '+str(i+1)
  store.set('theme_library',{p['name']:p for p in profiles});self.w=Window(store,demo=True);self.w.show();QTest.qWait(20);self.d=SettingsEditor(self.w);self.d.show()
 def tearDown(self):
  if not self.d.closed:self.d.reject()
  self.d.deleteLater();self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(30);self.tmp.cleanup()
 def test_multiple_named_profiles_switch_persist_restart_and_edit_selected(self):
  d=self.d;d.themes.setCurrentIndex(d.themes.findData('base:custom'));d.set_color('spectrum','#BA91FF');d.gradient_checks['spectrum'].setChecked(True);d.set_gradient_end('spectrum','#6ACEBB');d.visual.setChecked(True);d.visual_style.setCurrentIndex(d.visual_style.findData('glow'));d.library_controls.save_named('나의 밤')
  d.set_color('accent','#FFAA66');d.library_controls.save_named('나의 낮');d.themes.setCurrentIndex(d.themes.findData('saved:나의 밤'));d.apply_preview();self.assertEqual(self.w.spectrum.color,'#BA91FF');self.assertNotEqual(self.w.theme['accent'],'#FFAA66');self.assertEqual(self.w.spectrum.color_end,'#6ACEBB')
  d.set_color('accent','#FCAA78');d.themes.setCurrentIndex(d.themes.findData('saved:나의 낮'));d.themes.setCurrentIndex(d.themes.findData('saved:나의 밤'));self.assertEqual(d.custom_draft['accent'],'#FCAA78');d.accept();saved=self.w.store.config();self.assertEqual(saved['custom_theme_name'],'나의 밤');self.assertEqual(saved['theme_library']['나의 밤']['colors']['accent'],'#FCAA78');self.assertEqual(saved['custom_theme']['accent'],'#FCAA78');self.assertIn('나의 낮',saved['theme_library'])
  again=SettingsEditor(self.w);self.assertEqual(again.active_saved_name,'나의 밤');self.assertEqual(again.themes.currentData(),'saved:나의 밤');again.reject();again.deleteLater()
 def test_rename_delete_and_cancel_restore_collection_and_actual_theme(self):
  d=self.d;before=deepcopy(self.w.config);saved=self.w.store.config();name=next(iter(d.library_draft));d.themes.setCurrentIndex(d.themes.findData('saved:'+name));d.library_controls.rename_named('새 이름');self.assertIn('새 이름',d.library_draft);self.assertNotIn(name,d.library_draft);d.library_controls.delete_named();self.assertNotIn('새 이름',d.library_draft);d.apply_preview();d.reject();self.assertEqual(self.w.config,before);self.assertEqual(self.w.store.config(),saved)
 def test_single_and_bundle_export_import_preserve_gradients_and_conflicts_copy(self):
  d=self.d;name=next(iter(d.library_draft));d.themes.setCurrentIndex(d.themes.findData('saved:'+name));single=self.root/'내 테마.json';bundle=self.root/'전체.json';d.library_controls.export_file(single);d.library_controls.export_file(bundle,True)
  expected=d.current_profile(name);self.assertEqual(read_profiles(single),[expected]);self.assertEqual(len(read_profiles(bundle)),2);old=deepcopy(d.library_draft);names=d.library_controls.import_file(bundle);self.assertEqual(len(names),2);self.assertTrue(all(n.endswith('(2)') for n in names))
  for key,value in old.items():self.assertEqual(d.library_draft[key],value)
  self.assertEqual(d.library_draft[names[0]]['gradients'],expected['gradients']);self.assertEqual(d.active_saved_name,names[0])
 def test_bad_import_is_atomic_and_duplicate_save_and_rename_do_not_overwrite(self):
  d=self.d;before=deepcopy(d.library_draft);bad=self.root/'bad.json';good=next(iter(before.values()));broken=deepcopy(good);broken['colors']['panel']='bad';bad.write_text(json.dumps({'format':FORMAT,'version':1,'themes':[good,broken]}),encoding='utf-8')
  with self.assertRaises(ValueError):d.library_controls.import_file(bad)
  for field,value in (('style',[]),('style',{})):
   broken=deepcopy(good);broken['visualizer'][field]=value;bad.write_text(json.dumps({'format':FORMAT,'version':1,'themes':[broken]}),encoding='utf-8')
   with self.assertRaises(ValueError):d.library_controls.import_file(bad)
  self.assertEqual(d.library_draft,before);names=list(before)
  with self.assertRaises(ValueError):d.library_controls.save_named(names[0])
  d.themes.setCurrentIndex(d.themes.findData('saved:'+names[0]))
  with self.assertRaises(ValueError):d.library_controls.rename_named(names[1])
  self.assertEqual(d.library_draft,before)
 def test_loading_theme_never_changes_audio_source_or_size(self):
  d=self.d;size=self.w.size()
  with patch.object(self.w.engine.player,'setSource') as source,patch.object(self.w.engine.player,'stop') as stop:
   for name in d.library_draft:d.themes.setCurrentIndex(d.themes.findData('saved:'+name));d.apply_preview();self.assertEqual(self.w.config['custom_theme_name'],name);self.assertEqual(self.w.size(),size)
   d.reject();source.assert_not_called();stop.assert_not_called()
 def test_empty_saved_library_does_not_respawn_deleted_defaults(self):
  d=self.d
  for name in list(d.library_draft):d.themes.setCurrentIndex(d.themes.findData('saved:'+name));d.library_controls.delete_named()
  d.accept();self.assertEqual(self.w.store.config()['theme_library'],{});again=SettingsEditor(self.w);self.assertEqual(again.library_draft,{});again.reject();again.deleteLater()
 def test_existing_custom_draft_is_not_replaced_by_new_bundled_profiles(self):
  fresh=Store(self.root/'fresh').config();self.assertEqual(fresh['theme_library'],{});self.assertEqual(fresh['custom_theme'],{});self.assertEqual(library_profiles(None),{});self.assertEqual(self.d.themes.currentData(),'base:silver_blue')
 def test_bundled_theme_contrast_and_independent_wave_colors(self):
  def luminance(color):
   values=[int(color[i:i+2],16)/255 for i in (1,3,5)];linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values];return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
  for p in bundled_profiles():
   self.assertNotEqual(p['colors']['spectrum'],p['colors']['accent']);self.assertTrue(all(g['enabled'] for g in p['gradients'].values()))
   for bg in (p['colors']['panel'],p['gradients']['panel']['end'],p['colors']['bg'],p['gradients']['bg']['end']):
    a,b=sorted((luminance(p['colors']['text']),luminance(bg)));self.assertGreaterEqual((b+.05)/(a+.05),4.5)
class ThemeFileTests(unittest.TestCase):
 def test_format_roundtrip_filters_extra_paths_and_checks_version_and_name(self):
  profile=deepcopy(bundled_profiles()[0]);profile.update(background='C:/personal/background.png',music_roots=['Z:/Music']);text=encode_profiles([profile]);self.assertNotIn('personal',text);self.assertNotIn('music_roots',text);self.assertEqual(decode_profiles(text),[bundled_profiles()[0]])
  for name in ('','  ','line\nbreak','a'*61):
   with self.assertRaises(ValueError):theme_name(name)
  for text in ('[]','{}','null','{"format":"desktop-music-player-themes","version":99,"themes":[]}', 'invalid'):
   with self.assertRaises(ValueError):decode_profiles(text)
 def test_collision_names_remain_unique_and_length_bounded(self):
  self.assertEqual(unique_name('Night',['night']),'Night (2)');self.assertEqual(unique_name('Night',['night','Night (2)']),'Night (3)');self.assertLessEqual(len(unique_name('a'*60,['a'*60])),60)
