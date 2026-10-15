import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from desktop_music_player.core import Track,Queue,scan_library,youtube_input
from desktop_music_player.storage import Store
class CoreTests(unittest.TestCase):
    def test_scan_deduplicates_and_ignores_non_audio(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'sub').mkdir();(root/'sub'/'song.MP3').touch();(root/'cover.jpg').touch();(root/'clip.MP4').touch();(root/'sub'/'movie.mkv').touch()
            files=scan_library([root,root/'sub'])
            self.assertEqual([t.title for t in files],['clip','movie','song']);self.assertTrue(all(t.kind=='local' for t in files))
    def test_shuffle_no_repeats_and_repeat_cycles(self):
        q=Queue([Track(str(n),str(n)) for n in range(4)]);q.set_shuffle(True)
        heard=[q.next().uri for _ in range(4)]
        self.assertEqual(len(set(heard)),4);self.assertIsNone(q.next())
        q.repeat='all';self.assertIsNotNone(q.next())
    def test_remove_current_and_next_preserve_cursor(self):
        q=Queue([Track(str(n),str(n)) for n in range(4)]);q.select(2)
        self.assertFalse(q.remove(0));self.assertEqual(q.current.uri,'2')
        self.assertTrue(q.remove(1));self.assertEqual(q.next().uri,'3')
    def test_repeat_one_and_previous(self):
        q=Queue([Track('a','a'),Track('b','b')]);q.next();q.next();q.repeat='one'
        self.assertEqual(q.next(automatic=True).uri,'b');self.assertEqual(q.previous().uri,'a')
    def test_url_validation(self):
        for value in ['file:///etc/passwd','https://youtube.com.evil.test/a','http://localhost/a','https://user@youtube.com/a']:
            with self.assertRaises(ValueError):youtube_input(value)
        self.assertEqual(youtube_input('music'),'ytsearch10:music')
    def test_mixed_playlist_persists_order_and_deletes(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);tracks=[Track('Local','C:/personal/song.mp3'),Track('YouTube','https://youtu.be/dQw4w9WgXcQ','youtube')]
            store.save_playlist('Mix',tracks)
            again=Store(d);self.assertEqual([t.kind for t in again.playlist('Mix')],['local','youtube'])
            again.delete_playlist('Mix');self.assertEqual(again.playlist_names(),[])
    def test_portable_default_and_private_config(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);self.assertEqual(store.config()['music_roots'],['./music'])
            (Path(d)/'local.json').write_text('{"music_roots":["X:/Music"]}')
            self.assertEqual(store.roots(),['X:/Music'])
            store.set('music_roots',['Y:/Songs']);self.assertEqual(store.roots(),['Y:/Songs'])
    def test_library_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);store.save_library([Track('x','x')]);self.assertEqual(store.library()[0].uri,'x')
class YoutubeTests(unittest.TestCase):
    def test_search_is_flat_and_validates_video_ids(self):
        from desktop_music_player import youtube
        fake=Mock();fake.extract_info.return_value={'entries':[{'id':'dQw4w9WgXcQ','title':'Song'},{'id':'invalid','title':'Invalid'}]}
        with patch.object(youtube.yt_dlp,'YoutubeDL') as ydl:
            ydl.return_value.__enter__.return_value=fake
            tracks=youtube.search('Song')
        self.assertEqual(len(tracks),1);self.assertEqual(tracks[0].kind,'youtube')
        self.assertTrue(ydl.call_args.args[0]['extract_flat'])
    def test_stream_resolution_is_not_persisted(self):
        from desktop_music_player import youtube
        t=Track('x','https://youtu.be/dQw4w9WgXcQ','youtube');fake=Mock()
        fake.extract_info.return_value={'url':'https://example.test/transient?sig=secret','title':'Real title','vcodec':'none'}
        with patch.object(youtube.yt_dlp,'YoutubeDL') as ydl:
            ydl.return_value.__enter__.return_value=fake
            stream=youtube.resolve(t)
        self.assertIn('sig=',stream['url']);self.assertNotIn('sig=',str(t.to_dict()))
if __name__=='__main__':unittest.main()
