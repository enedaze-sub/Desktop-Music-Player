"""Bounded background jobs and virtualized track list."""
import json,uuid
from PySide6.QtCore import QObject,Signal,QRunnable,Qt,QAbstractListModel,QModelIndex,QMimeData
class Signals(QObject):
    done=Signal(int,object,str)
class Job(QRunnable):
    def __init__(self,ident,function,*args):
        super().__init__();self.ident=ident;self.function=function;self.args=args;self.signals=Signals()
    def run(self):
        try:self.signals.done.emit(self.ident,self.function(*self.args),'')
        except Exception as error:
            # Do not expose signed media URLs or credential-like request internals.
            message=str(error) if isinstance(error,(ValueError,FileNotFoundError)) else '처리하지 못했습니다. 연결이나 파일 상태를 확인해 주세요.'
            self.signals.done.emit(self.ident,None,message[:300])
class TrackModel(QAbstractListModel):
    def __init__(self,tracks=None,parent=None):super().__init__(parent);self.tracks=list(tracks or [])
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.tracks)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid() or index.row()>=len(self.tracks):return None
        t=self.tracks[index.row()]
        if role==Qt.DisplayRole:return t.title+'\n'+('YOUTUBE' if t.kind=='youtube' else 'LOCAL')+'  ·  '+(t.artist or t.album)
        if role==Qt.ToolTipRole:return t.title+'\n'+t.album
        if role==Qt.UserRole:return t
        if role==Qt.SizeHintRole:
            from PySide6.QtCore import QSize
            return QSize(100,54)
    def replace(self,tracks):
        self.beginResetModel();self.tracks=list(tracks);self.endResetModel()

class QueueModel(TrackModel):
    move_requested=Signal(list,int)
    MIME='application/x-desktop-music-player-queue'
    def __init__(self,queue,parent=None):
        super().__init__(queue.tracks,parent);self.queue=queue;self.active=False;self.token=uuid.uuid4().hex
    def replace(self,tracks):
        self.token=uuid.uuid4().hex;super().replace(tracks)
    def data(self,index,role=Qt.DisplayRole):
        if role==Qt.UserRole+1 and index.isValid():
            row=index.row();current=self.queue.index
            if row==current:return '현재곡' if self.active else '선택곡'
            if self.queue.shuffle:return '셔플 대기'
            offset=row-current
            if current>=0 and offset<0:return '이전곡'
            return '다음곡' if offset==1 else f'예약 {offset}'
        return super().data(index,role)
    def flags(self,index):return super().flags(index)|Qt.ItemIsDragEnabled if index.isValid() else Qt.ItemIsDropEnabled
    def supportedDropActions(self):return Qt.MoveAction
    def mimeTypes(self):return [self.MIME]
    def mimeData(self,indexes):
        mime=QMimeData();mime.setData(self.MIME,json.dumps({'token':self.token,'rows':sorted({i.row() for i in indexes if i.isValid()})}).encode());return mime
    def dropMimeData(self,mime,action,row,column,parent):
        if action==Qt.IgnoreAction:return True
        if action!=Qt.MoveAction or not mime.hasFormat(self.MIME):return False
        try:
            data=json.loads(bytes(mime.data(self.MIME)));rows=data['rows']
            if data['token']!=self.token or not rows or any(type(i)!=int or not 0<=i<len(self.tracks) for i in rows):return False
        except (ValueError,KeyError,TypeError):return False
        destination=row if row>=0 else parent.row() if parent.isValid() else len(self.tracks)
        if not 0<=destination<=len(self.tracks):return False
        self.move_requested.emit(rows,destination);return True
    def refresh_state(self,active):
        self.active=active
        if self.tracks:self.dataChanged.emit(self.index(0,0),self.index(len(self.tracks)-1,0),[Qt.UserRole+1])
