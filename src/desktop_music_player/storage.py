"""Atomic, project-local state; private paths never enter source defaults."""
import json,sqlite3
from contextlib import contextmanager
from pathlib import Path
from .core import Track,app_root
DEFAULTS={'music_roots':['./music'],'volume':0.3,'theme':'silver_blue','opacity':1.0,'accent':'','background':'','always_on_top':False,'visualizer':False,'width':600,'panel_height':340,'repeat':'off','shuffle':False}
class Store:
    def __init__(self,folder=None):
        self.folder=Path(folder or app_root()/'data');self.folder.mkdir(parents=True,exist_ok=True)
        self.db=self.folder/'player.sqlite3'
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS library(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS playlists(name TEXT PRIMARY KEY,tracks TEXT NOT NULL)')
    @contextmanager
    def connect(self):
        conn=sqlite3.connect(self.db,timeout=5)
        try:
            with conn:yield conn
        finally:conn.close()
    def config(self):
        data=dict(DEFAULTS)
        personal=self.folder/'local.json'
        if personal.exists():
            try:data.update(json.loads(personal.read_text(encoding='utf-8-sig')))
            except (OSError,ValueError):pass
        with self.connect() as c:
            data.update({key:json.loads(value) for key,value in c.execute('SELECT key,value FROM settings')})
        data['volume']=max(0,min(1,float(data['volume'])))
        data['opacity']=max(.35,min(1,float(data['opacity'])))
        return data
    def set(self,key,value):
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value,ensure_ascii=False)))
    def roots(self):
        return [str((app_root()/p).resolve()) if not Path(p).is_absolute() else p for p in self.config()['music_roots']]
    def save_library(self,tracks):
        with self.connect() as c:
            c.execute('DELETE FROM library')
            c.executemany('INSERT INTO library VALUES(?,?)',[(t.key,json.dumps(t.to_dict(),ensure_ascii=False)) for t in tracks])
    def library(self):
        with self.connect() as c:return [Track.from_dict(json.loads(row[0])) for row in c.execute('SELECT payload FROM library ORDER BY id')]
    def save_playlist(self,name,tracks):
        name=name.strip()
        if not 1<=len(name)<=80:raise ValueError('재생목록 이름은 1~80자로 입력하세요.')
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO playlists VALUES(?,?)',(name,json.dumps([t.to_dict() for t in tracks],ensure_ascii=False)))
    def playlist_names(self):
        with self.connect() as c:return [row[0] for row in c.execute('SELECT name FROM playlists ORDER BY name')]
    def playlist(self,name):
        with self.connect() as c:row=c.execute('SELECT tracks FROM playlists WHERE name=?',(name,)).fetchone()
        return [Track.from_dict(x) for x in json.loads(row[0])] if row else []
    def delete_playlist(self,name):
        with self.connect() as c:c.execute('DELETE FROM playlists WHERE name=?',(name,))
