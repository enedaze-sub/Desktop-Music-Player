"""Render theme/spectrum samples and measure the small FFT and painter costs."""
import os,sys,json,time,statistics,math,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts,COMPACT_HEIGHT
from desktop_music_player.storage import Store
from desktop_music_player.settings_editor import SettingsEditor
from desktop_music_player.palettes import STYLES
from desktop_music_player.spectrum_analysis import SpectrumAnalyzer
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/appearance-v022';ART.mkdir(parents=True,exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False);configure_fonts();report={}
with tempfile.TemporaryDirectory() as state:
 w=Window(Store(state),demo=True);w.show();w.config['visualizer']=True;w.title.setText('오늘의 플레이리스트 · My Favorite Songs');w.tell('재생 준비 완료')
 d=SettingsEditor(w);d.show();d.visual.setChecked(True)
 for i,t in enumerate(w.themes):
  d.themes.setCurrentIndex(i);d.apply_preview();QTest.qWait(80);d.grab().save(str(ART/('settings-'+t['id']+'.png')))
 for n,theme_id in enumerate(('sunset_apricot','lavender_aurora')):
  d.themes.setCurrentIndex(d.themes.findData('base:'+theme_id));d.apply_preview();QTest.qWait(80);d.grab().save(str(ART/('builtin-theme-'+str(n)+'.png')));w.spectrum.levels=[.12+.82*abs(math.sin(i*.3)) for i in range(24)];w.grab().save(str(ART/('builtin-player-'+str(n)+'.png')))
 d.themes.setCurrentIndex(d.themes.findData('base:custom'))
 d.set_color('bg','#201921');d.set_color('panel','#332533');d.set_color('accent','#F5A873');d.set_color('text','#FFF0E6');d.set_color('muted','#CBB3C2');d.set_color('border','#79586D');d.set_color('spectrum','#D4C3FF')
 for key,end in (('bg','#183044'),('panel','#243857'),('accent','#F2CF88'),('spectrum','#69C8FF')):
  d.gradient_checks[key].setChecked(True);d.set_gradient_end(key,end);d.gradient_directions[key].setCurrentIndex(0)
 render={}
 for style in STYLES:
  d.visual_style.setCurrentIndex(d.visual_style.findData(style));d.apply_preview();QTest.qWait(80);d.grab().save(str(ART/('settings-custom-'+style+'.png')))
  for width in (560,1600):
   w.resize(w.px(width),w.height());app.processEvents();w.spectrum.levels=[.12+.82*abs(math.sin(i*.3)) for i in range(24)];w.grab().save(str(ART/(style+'-'+str(width)+'.png')))
  values=[]
  for _ in range(80):
   start=time.perf_counter();w.spectrum.grab();values.append((time.perf_counter()-start)*1000)
  render[style]={'median_ms':round(statistics.median(values),3),'p95_ms':round(sorted(values)[int(len(values)*.95)],3)}
 report['spectrum_paint']=render;report['settings_preview_in_dialog']=True;report['styles']=list(STYLES);d.reject();d.deleteLater()
 w.config['visualizer']=True;w.config['visualizer_style']='glow'
 for factor in (.5,.8,1.5):
  w.set_ui_scale(factor,persist=False);w.resize(w.px(560),w.px(COMPACT_HEIGHT));w.apply_theme();app.processEvents();w.spectrum.levels=[.12+.82*abs(math.sin(i*.3)) for i in range(24)];w.grab().save(str(ART/('minimum-'+str(factor)+'.png')))
 w.engine.stop();w.hide();w.deleteLater();QTest.qWait(30)
analyzer=SpectrumAnalyzer();samples=(.01*np.sin(2*np.pi*440*np.arange(2048)/48000)).astype(np.float32);values=[]
for _ in range(300):
 start=time.perf_counter();analyzer.analyze(samples,48000);values.append((time.perf_counter()-start)*1000)
report['fft_analysis']={'median_ms':round(statistics.median(values),3),'p95_ms':round(sorted(values)[int(len(values)*.95)],3)}
report['render_rate_limit_fps']=20
(ART/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
