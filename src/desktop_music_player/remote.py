"""Background command channel on the single-instance socket, for other local programs and automation tools.
A client writes one JSON line and reads one JSON line back; the window is not raised or clicked.
Anything that is not a JSON line (the second instance's b'show') still just restores the window.

Commands: {"cmd":"search","source":"local"|"youtube","q":"...","limit":20} → tracks with a 0~1 match score
          {"cmd":"play","source":...,"i":n}  plays result n of the last search of that source
          {"cmd":"pause"|"resume"|"toggle"|"next"|"prev"|"shuffle"|"now"|"show"}  {"cmd":"volume","value":0~100}
"""
import json,re
from . import youtube

SPLIT=re.compile(r'[\s\-_·,.!?~/()\[\]（）【】「」『』〈〉《》"\']+')
BRACKETS=re.compile(r'[(\[（【「『][^)\]）】」』]*[)\]）】」』]')

def words(text):return [w for w in SPLIT.split(text.casefold()) if len(w)>=2]
def bigrams(text):return {text[i:i+2] for i in range(len(text)-1)}

def score(track,query):
    """Share of query words found in title/artist/album; a word that is only close (空色のデイズ vs 空色デイズ) counts 0.8.
    Words in brackets are often romanization or translation, so the score without them is also tried."""
    hay=(track.title+' '+track.artist+' '+track.album).casefold();grams=bigrams(hay.replace(' ',''))
    def part(ws):
        if not ws:return 0
        hit=0
        for w in ws:
            if w in hay:hit+=1
            elif len(w)>=3 and len(bigrams(w)&grams)>=0.6*len(bigrams(w)):hit+=0.8
        return hit/len(ws)
    return round(max(part(words(query)),part(words(BRACKETS.sub(' ',query)))),2)

def info(track,match=None):
    data={'title':track.title,'artist':track.artist,'album':track.album,'kind':track.kind,'duration':track.duration}
    if match is not None:data['score']=match
    return data

class RemoteControl:
    def __init__(self,window):self.window=window;self.found={'local':[],'youtube':[]}
    def attach(self,connection):
        buffer=bytearray();state={'handled':False}
        def ready():
            buffer.extend(bytes(connection.readAll()))
            if state['handled'] or b'\n' not in buffer:return
            state['handled']=True
            try:request=json.loads(bytes(buffer).split(b'\n',1)[0].decode('utf-8'))
            except ValueError:request=None
            if not isinstance(request,dict):connection.disconnectFromServer();self.window.restore();return
            try:self.handle(request,lambda reply:self.reply(connection,reply))
            except Exception as error:self.reply(connection,{'ok':False,'error':str(error)})
        def gone():
            if not state['handled']:self.window.restore()
            connection.deleteLater()
        connection.readyRead.connect(ready);connection.disconnected.connect(gone)
        if connection.bytesAvailable():ready()
    @staticmethod
    def reply(connection,data):
        if connection.state()!=connection.LocalSocketState.ConnectedState:return
        connection.write((json.dumps(data,ensure_ascii=False)+'\n').encode('utf-8'));connection.flush();connection.disconnectFromServer()
    def handle(self,request,answer):
        w=self.window;cmd=request.get('cmd')
        if cmd=='search':return self.search(request.get('source','local'),str(request.get('q','')).strip(),int(request.get('limit',20)),answer)
        if cmd=='play':
            found=self.found.get(request.get('source','local'),[]);i=int(request.get('i',0))
            if not 0<=i<len(found):return answer({'ok':False,'error':'먼저 검색해 주세요'})
            row=len(w.queue.tracks);w.queue.append([found[i]]);w.play_index(row);w.tell(f'요청한 곡을 재생해요: {found[i].title}')
        elif cmd in ('pause','resume','toggle'):
            if cmd=='toggle' or w.engine.playing()==(cmd=='pause'):w.toggle_play()
        elif cmd=='next':w.next()
        elif cmd=='prev':w.previous()
        elif cmd=='shuffle':w.random_local()
        elif cmd=='volume':w.volume.setValue(max(0,min(100,int(request.get('value',w.volume.value())))))
        elif cmd=='show':w.restore()
        elif cmd!='now':return answer({'ok':False,'error':f'모르는 명령: {cmd}'})
        answer({'ok':True,**self.now()})
    def now(self):
        w=self.window;track=w.queue.current if w.engine.track else None
        return {'track':info(track) if track else None,'playing':w.engine.playing(),'loading':bool(w.engine.loading),
                'position':w.engine.playback_position()/1000 if track else 0,'volume':w.volume.value()}
    def search(self,source,query,limit,answer):
        if not query:return answer({'ok':False,'error':'검색어가 비었어요'})
        if source=='local':
            ranked=sorted(((score(t,query),t) for t in self.window.library),key=lambda pair:-pair[0])
            ranked=[pair for pair in ranked[:limit] if pair[0]>0];self.found['local']=[t for _,t in ranked]
            return answer({'ok':True,'tracks':[info(t,s) for s,t in ranked]})
        if source!='youtube':return answer({'ok':False,'error':f'모르는 곳: {source}'})
        session=youtube.SearchSession(query)
        def done(result,error):
            session.close()
            if error or not result:return answer({'ok':False,'error':error or '유튜브 검색 실패'})
            tracks=result['tracks'][:limit];self.found['youtube']=tracks
            answer({'ok':True,'tracks':[info(t,score(t,query)) for t in tracks]})
        self.window.submit(session.get_page,(0,),done,report_error=False)
