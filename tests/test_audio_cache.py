import os,sys,tempfile,json,unittest,time
from pathlib import Path
from threading import Event
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from desktop_music_player import audio_cache,youtube
from desktop_music_player.core import Track
class AudioCacheTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.track=Track('Song','https://youtu.be/00000000001','youtube');self.result={'url':'https://example.test/audio?sig=SECRET','title':'Song','duration':90,'audio_format':'140','video_url':'https://example.test/video?sig=SECRET'}
 def tearDown(self):self.temp.cleanup()
 def downloader(self):
  fake=Mock();fake.params={};fake.prepare_filename.side_effect=lambda info:fake.params['outtmpl']['default'].replace('%(ext)s','m4a');fake.process_info.side_effect=lambda info:Path(fake.prepare_filename(info)).write_bytes(b'audio');return fake
 def test_complete_cache_reuses_audio_without_persisting_signed_urls(self):
  fake=self.downloader();result=audio_cache.prepare(fake,{'ext':'m4a','filesize':5},self.result,self.folder,self.track);self.assertTrue(Path(result['audio_path']).is_file());meta=(self.folder/(self.track.key+'.json')).read_text();self.assertNotIn('SECRET',meta);self.assertNotIn('https://',meta)
  with patch.object(youtube.yt_dlp,'YoutubeDL') as network:
   hit=youtube.resolve(self.track,cache_folder=self.folder);network.assert_not_called();self.assertEqual(hit['audio_path'],result['audio_path']);self.assertIsNone(hit['url'])
 def test_large_or_long_media_stays_streamed_without_unbounded_download(self):
  for info in ({'filesize':audio_cache.MAX_FILE+1},{'duration':1801},{'is_live':True},{'live_status':'is_live'}):
   fake=self.downloader();result=audio_cache.prepare(fake,info,self.result,self.folder,self.track);fake.process_info.assert_not_called();self.assertNotIn('audio_path',result)
 def test_cancelled_partial_is_not_published(self):
  fake=self.downloader();cancel=Event();cancel.set();self.assertIsNone(audio_cache.cached_audio(self.folder,self.track))
  with self.assertRaises(ValueError):audio_cache.prepare(fake,{'ext':'m4a'},self.result,self.folder,self.track,cancel)
  self.assertFalse((self.folder/(self.track.key+'.json')).exists())
 def test_progress_cancellation_removes_only_its_partial(self):
  fake=self.downloader();cancel=Event();unrelated=self.folder/'personal.txt';unrelated.write_text('keep')
  def download(info):
   Path(fake.prepare_filename(info)+'.part').write_bytes(b'partial');cancel.set();fake.add_progress_hook.call_args.args[0]({'downloaded_bytes':7})
  fake.process_info.side_effect=download
  with self.assertRaises(ValueError):audio_cache.prepare(fake,{'ext':'m4a'},self.result,self.folder,self.track,cancel)
  self.assertEqual(list(self.folder.glob('*.part')),[]);self.assertEqual(unrelated.read_text(),'keep')
 def test_pruning_protects_current_and_ignores_unrelated_files(self):
  current=self.folder/(self.track.key+'.m4a');current.write_bytes(b'current');old=self.folder/('f'*24+'.m4a');old.write_bytes(b'old');other=self.folder/'unrelated.txt';other.write_bytes(b'keep')
  with patch.object(audio_cache,'MAX_TRACKS',1):audio_cache.prune(self.folder,{self.track.key})
  self.assertTrue(current.exists());self.assertFalse(old.exists());self.assertTrue(other.exists())
 def test_invalid_manifest_and_size_mismatch_are_not_played(self):
  manifest=self.folder/(self.track.key+'.json');manifest.write_text(json.dumps({'filename':'../outside.m4a'}));self.assertIsNone(audio_cache.cached_audio(self.folder,self.track))
  fake=self.downloader();audio_cache.prepare(fake,{'ext':'m4a'},self.result,self.folder,self.track);file=next(self.folder.glob('*.m4a'));file.write_bytes(b'broken size');self.assertIsNone(audio_cache.cached_audio(self.folder,self.track))
