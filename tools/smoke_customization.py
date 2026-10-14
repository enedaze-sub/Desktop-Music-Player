"""Capture appearance editing with inert demo tracks; no private image or media."""
import os,sys,json
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.background_editor import BackgroundEditor
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts'/'customization';OUT.mkdir(parents=True,exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False);configure_fonts();w=Window(Store(OUT/'state'),demo=True)
tracks=[Track('밤의 플레이리스트 · Night Walk','demo.mp3',album='미리보기'),Track('오늘의 작은 쉼표','demo2.mp3',album='미리보기')];w.set_library(tracks);w.show();QTest.qWait(50)
d=SettingsEditor(w);d.show();QTest.qWait(80);d.grab().save(str(OUT/'settings.png'));settings_size=[d.width(),d.height()];d.themes.setCurrentIndex(2);d.opacity.slider.setValue(25);d.scale.slider.setValue(90);QTest.qWait(90);w.grab().save(str(OUT/'live-preview.png'));d.reject();d.deleteLater()
e=BackgroundEditor(w);e.draft['background']=str(ROOT/'assets'/'default-cover.png');e.sync_controls();e.show();QTest.qWait(100);e.grab().save(str(OUT/'background-compact.png'));image_key=e.preview_window.surface.image.cacheKey()
e.view.setCurrentIndex(1);e.mode.setCurrentIndex(2);e.list_transparency.setValue(60);e.transparency.setValue(20);e.zoom.setValue(120);QTest.qWait(100);e.grab().save(str(OUT/'background-expanded.png'))
assert not w.expanded;assert e.preview_window.expanded
area=w.screen().availableGeometry();assert e.width()<=area.width()-20 and e.height()<=area.height()-40,(e.size(),area)
assert settings_size[0]<=area.width()-20 and settings_size[1]<=area.height()-40,(settings_size,area)
report={'settings_size':settings_size,'background_size':[e.width(),e.height()],'live_preview_passed':True,'expanded_preview_preserves_actual_drawer':not w.expanded,'image_cache_reused':image_key==e.preview_window.surface.image.cacheKey()}
assert report['image_cache_reused'];(OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report);e.reject();e.deleteLater();w.engine.stop();w.hide();w.deleteLater();QTest.qWait(60)
