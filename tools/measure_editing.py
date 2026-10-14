"""Reproducible editing latency probe with a generated 4K image and fake library."""
import os,sys,tempfile,time,json,statistics,cProfile,pstats,io
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QTest
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from desktop_music_player.core import Track
from desktop_music_player.background_editor import BackgroundEditor
from desktop_music_player.settings_editor import SettingsEditor
ROOT=Path(__file__).resolve().parents[1];(ROOT/'artifacts').mkdir(exist_ok=True);app=QApplication([]);configure_fonts();report={}
with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as temp:
 image=QImage(4096,2304,QImage.Format_RGB32)
 for y in range(2304):
  from PySide6.QtGui import QPainter
  if y==0:p=QPainter(image)
  p.setPen(QColor(y%255,(y*3)%255,90));p.drawLine(0,y,4095,y)
 p.end();file=Path(temp)/'4k.png';image.save(str(file))
 w=Window(Store(Path(temp)/'state'),demo=True);w.set_library([Track(f'미리보기 곡 {n}','demo.mp3',album='성능 검증') for n in range(12926)]);w.show();e=BackgroundEditor(w);e.draft['background']=str(file);e.view.setCurrentIndex(1);e.mode.setCurrentIndex(2);e.show();e.render_preview();QTest.qWait(50)
 def measure(label,fn):
  values=[]
  for i in range(45):
   start=time.perf_counter();fn(i);values.append((time.perf_counter()-start)*1000)
  report[label]={'median_ms':round(statistics.median(values),2),'p95_ms':round(sorted(values)[int(len(values)*.95)],2),'max_ms':round(max(values),2)}
 profiler=cProfile.Profile();profiler.enable()
 measure('background_zoom',lambda i:(e.zoom.setValue(75+i*2),e.render_preview()))
 measure('background_drag',lambda i:(e.move_image(.004,-.002),e.render_preview()))
 profiler.disable();text=io.StringIO();pstats.Stats(profiler,stream=text).sort_stats('cumtime').print_stats(18);(ROOT/'artifacts'/'editing-profile.txt').write_text(text.getvalue(),encoding='utf-8')
 e.reject();e.deleteLater();QTest.qWait(30);d=SettingsEditor(w);d.show()
 measure('window_opacity',lambda i:(d.opacity.setValue(i%40),d.apply_preview()))
 profiler=cProfile.Profile();profiler.enable()
 measure('ui_scale',lambda i:(d.scale.setValue(70+i%35),d.apply_preview()))
 profiler.disable();text=io.StringIO();pstats.Stats(profiler,stream=text).sort_stats('cumtime').print_stats(14);(ROOT/'artifacts'/'editing-scale-profile.txt').write_text(text.getvalue(),encoding='utf-8')
 d.reject();d.deleteLater();w.hide();w.deleteLater();QTest.qWait(60)
name=sys.argv[1] if len(sys.argv)>1 else 'editing-latency.json';(ROOT/'artifacts'/name).write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
