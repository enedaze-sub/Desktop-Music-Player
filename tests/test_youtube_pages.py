import os,sys,tempfile,unittest,threading
from pathlib import Path
from unittest.mock import Mock,patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from desktop_music_player import youtube
from desktop_music_player.core import Track
from desktop_music_player.app import Window,configure_fonts
from desktop_music_player.storage import Store
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
class SearchPagesTests(unittest.TestCase):
 def test_lazy_continuation_and_cached_previous_page(self):
  consumed=[]
  def entries():
   for i in range(25):consumed.append(i);yield {'id':f'{i:011d}','title':f'Song {i}'}
  fake=Mock();fake.extract_info.return_value={'entries':entries()}
  with patch.object(youtube.yt_dlp,'YoutubeDL') as factory:
   factory.return_value.__enter__.return_value=fake;s=youtube.SearchSession('Song')
   a=s.get_page(0);self.assertEqual(len(consumed),11);self.assertEqual(len(a['tracks']),10);self.assertTrue(a['has_more'])
   b=s.get_page(1);self.assertEqual(len(consumed),21);self.assertEqual(b['tracks'][0].title,'Song 10');self.assertEqual(s.get_page(0),a);self.assertEqual(len(consumed),21)
   c=s.get_page(2);self.assertEqual(len(c['tracks']),5);self.assertFalse(c['has_more']);fake.extract_info.assert_called_once_with('ytsearchall:Song',download=False,process=False);self.assertTrue(factory.call_args.args[0]['lazy_playlist']);s.close()
 def test_real_ytdlp_keeps_unvisited_search_results_lazy(self):
  # Exercise the actual yt-dlp processing boundary: mocking extract_info hid
  # its eager playlist processing even with lazy_playlist=True.
  from yt_dlp.extractor.youtube import YoutubeSearchIE
  consumed=[]
  def entries(*_):
   for i in range(100):
    consumed.append(i)
    if len(consumed)>21:raise AssertionError('Fetched unrequested search results')
    yield {'_type':'url','ie_key':'Youtube','id':f'{i:011d}','title':f'Song {i}','url':f'https://www.youtube.com/watch?v={i:011d}'}
  with patch.object(YoutubeSearchIE,'_search_results',entries):
   s=youtube.SearchSession('Song')
   try:
    first=s.get_page(0);self.assertEqual(len(first['tracks']),10);self.assertEqual(len(consumed),11)
    second=s.get_page(1);self.assertEqual(len(second['tracks']),10);self.assertEqual(len(consumed),21)
    self.assertEqual(s.get_page(0),first);self.assertEqual(len(consumed),21)
   finally:s.close()
 def test_deleted_live_invalid_and_duplicate_entries_are_skipped(self):
  entries=[None,{'id':'bad'},{'id':'00000000001','title':'[Private video]'},{'id':'00000000002','is_live':True},{'id':'00000000003','title':'Song'},{'id':'00000000003','title':'Duplicate'}]
  fake=Mock();fake.extract_info.return_value={'entries':iter(entries)}
  with patch.object(youtube.yt_dlp,'YoutubeDL') as factory:
   factory.return_value.__enter__.return_value=fake;s=youtube.SearchSession('Song');a=s.get_page(0);self.assertEqual(len(a['tracks']),1);self.assertFalse(a['has_more']);s.close()
 def test_error_retry_keeps_cached_results_and_deduplicates(self):
  def broken():
   for i in range(12):yield Track(str(i),f'{i}')
   raise OSError('offline')
  def restored():
   for i in range(24):yield Track(str(i),f'{i}')
  s=youtube.SearchSession('Song')
  with patch.object(s,'_iter_tracks',side_effect=[broken(),restored()]):
   first=s.get_page(0)
   with self.assertRaises(OSError):s.get_page(1)
   second=s.get_page(1);self.assertEqual([t.title for t in second['tracks']],[str(i) for i in range(10,20)]);self.assertEqual(s.get_page(0),first);s.close()
 def test_cancel_does_not_wait_for_inflight_network(self):
  ready=threading.Event();release=threading.Event();closed=[];errors=[]
  def blocked():
   try:ready.set();release.wait(2);yield Track('Song','song')
   finally:closed.append(True)
  s=youtube.SearchSession('Song')
  def work():
   try:s.get_page(0)
   except ValueError as error:errors.append(error)
  with patch.object(s,'_iter_tracks',side_effect=blocked):
   thread=threading.Thread(target=work);thread.start();self.assertTrue(ready.wait(1));s.close();self.assertFalse(release.is_set());release.set();thread.join(2);self.assertFalse(thread.is_alive());self.assertTrue(closed);self.assertTrue(errors)
 def test_video_and_playlist_urls_preserve_existing_result_behavior(self):
  tracks=[Track('Song','https://youtu.be/dQw4w9WgXcQ','youtube')]
  for value in ('https://youtu.be/dQw4w9WgXcQ','https://youtube.com/playlist?list=PLexample'):
   with patch.object(youtube,'search',return_value=tracks) as search:
    s=youtube.SearchSession(value);self.assertFalse(s.paged);self.assertEqual(s.get_page(0)['tracks'],tracks);s.get_page(0);search.assert_called_once();s.close()
class SearchPageUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);configure_fonts()
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.w=Window(Store(self.temp.name),demo=True);self.w.show();QTest.qWait(20)
 def tearDown(self):
  if self.w.youtube_session:self.w.youtube_session.close()
  self.w.engine.stop();self.w.hide();self.w.deleteLater();QTest.qWait(20);self.temp.cleanup()
 def test_buttons_page_selection_and_local_switch(self):
  w=self.w;w.change_source('youtube');w.expand('보관함');w.finish_transition();w.search_box.setText('Song');calls=[]
  def submit(fn,args,callback,**kwargs):calls.append((args[0],callback))
  with patch.object(w,'submit',side_effect=submit):
   w.search();self.assertFalse(w.youtube_next.isEnabled());tracks=[Track(str(i),str(i),'youtube') for i in range(10)];calls[-1][1]({'tracks':tracks,'page':0,'has_more':True},'');self.assertTrue(w.youtube_next.isEnabled());w.youtube_next.click();self.assertEqual(calls[-1][0],1)
   second=[Track('second','second','youtube')];calls[-1][1]({'tracks':second,'page':1,'has_more':False},'');self.assertTrue(w.youtube_prev.isEnabled());self.assertFalse(w.youtube_next.isEnabled());w.add_all_button.click();self.assertEqual(w.queue.tracks,second)
   w.youtube_prev.click();self.assertEqual(calls[-1][0],0);calls[-1][1]({'tracks':tracks,'page':0,'has_more':True},'');w.change_source('local');self.assertTrue(w.youtube_pager.isHidden());w.change_source('youtube');self.assertFalse(w.youtube_pager.isHidden());self.assertEqual(w.search_box.text(),'Song');self.assertEqual(w.library_model.tracks,tracks)
 def test_late_results_and_errors_do_not_replace_new_query_or_local_view(self):
  w=self.w;calls=[]
  with patch.object(w,'submit',side_effect=lambda fn,args,callback,**kw:calls.append(callback)):
   w.change_source('youtube');w.search_box.setText('old');w.search();w.search_box.setText('new');w.search();old,new=calls;old({'tracks':[Track('old','old')],'page':0,'has_more':False},'');self.assertEqual(w.youtube_results,[])
   new({'tracks':[Track('new','new')],'page':0,'has_more':True},'');w.load_youtube_page(1);last=calls[-1];w.change_source('local');w.tell('local');last(None,'offline');self.assertEqual(w.status_label.text(),'local');self.assertEqual(w.library_model.tracks,[]);self.assertFalse(w.youtube_loading)
