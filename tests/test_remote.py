import unittest
from desktop_music_player.core import Track
from desktop_music_player.remote import RemoteControl,score

class FakeEngine:
    def __init__(self):self.track=None;self.loading=False;self.state=False
    def playing(self):return self.state
    def playback_position(self):return 0
class FakeQueue:
    def __init__(self):self.tracks=[];self.index=-1
    @property
    def current(self):return self.tracks[self.index] if 0<=self.index<len(self.tracks) else None
    def append(self,tracks):self.tracks+=tracks
class FakeVolume:
    def __init__(self):self.v=50
    def value(self):return self.v
    def setValue(self,v):self.v=v
class FakeWindow:
    def __init__(self,library):
        self.library=library;self.engine=FakeEngine();self.queue=FakeQueue();self.volume=FakeVolume();self.toggles=0;self.restored=0
    def play_index(self,i):self.queue.index=i;self.engine.track=self.queue.tracks[i];self.engine.state=True
    def toggle_play(self):self.toggles+=1;self.engine.state=not self.engine.state
    def tell(self,message):pass
    def restore(self):self.restored+=1

class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.library=[Track('空色デイズ','a.mp3',artist='中川翔子'),Track('HEART BEAT','b.mp3',artist='YOASOBI'),Track('アイドル','c.mp3',artist='YOASOBI')]
        self.window=FakeWindow(self.library);self.remote=RemoteControl(self.window)
    def ask(self,request):
        replies=[];self.remote.handle(request,replies.append);return replies[0]
    def test_score_counts_close_words_and_ignores_bracketed_romanization(self):
        self.assertEqual(score(self.library[0],'空色のデイズ(中川翔子)'),0.9)
        self.assertEqual(score(self.library[1],'YOASOBI アイドル'),0.5)
        self.assertEqual(score(Track('時間列車','d.mp3',artist='supercell'),'時間列車 (Jikan Ressha)'),1.0)
    def test_search_then_play_appends_and_plays(self):
        found=self.ask({'cmd':'search','source':'local','q':'YOASOBI アイドル'})
        self.assertTrue(found['ok']);self.assertEqual(found['tracks'][0]['title'],'アイドル');self.assertEqual(found['tracks'][0]['score'],1.0)
        played=self.ask({'cmd':'play','source':'local','i':0})
        self.assertEqual(played['track']['title'],'アイドル');self.assertTrue(played['playing']);self.assertEqual(len(self.window.queue.tracks),1)
    def test_pause_and_resume_do_not_toggle_twice(self):
        self.window.engine.state=True
        self.ask({'cmd':'pause'});self.ask({'cmd':'pause'});self.assertEqual(self.window.toggles,1)
        self.ask({'cmd':'resume'});self.ask({'cmd':'resume'});self.assertEqual(self.window.toggles,2)
    def test_volume_is_clamped_and_unknown_command_fails(self):
        self.assertEqual(self.ask({'cmd':'volume','value':130})['volume'],100)
        self.assertFalse(self.ask({'cmd':'jump'})['ok'])
        self.assertFalse(self.ask({'cmd':'play','source':'local','i':0})['ok'])

if __name__=='__main__':unittest.main()
