"""Native playback with lazy video and real decoded-audio spectrum."""
import time
from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject,QUrl,Signal,Slot,QThreadPool,QTimer
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput,QAudioBufferOutput,QAudioFormat
from .jobs import Job
from .youtube import resolve
class Engine(QObject):
    message=Signal(str)
    changed=Signal()
    ended=Signal()
    spectrum=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio)
        self.audio.setVolume(.3)
        self.capture=QAudioBufferOutput(self);self.capture.audioBufferReceived.connect(self.buffer)
        self.player.playbackStateChanged.connect(self.play_state)
        self.player.durationChanged.connect(lambda _:self.changed.emit())
        self.player.mediaStatusChanged.connect(self.status)
        self.player.errorOccurred.connect(self.error)
        self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1)
        self.track=None;self.video=False;self.loading=False;self.request=0;self.jobs={};self.cache={};self.seek=0;self.autoplay=True;self.last_buffer=0;self.visual_enabled=False;self.video_player=None;self.video_widget=None
    def playing(self):return self.player.playbackState()==QMediaPlayer.PlayingState
    def play_track(self,track,video=False,position=0,autoplay=True):
        self.request+=1;request=self.request
        self.player.stop();
        if self.video_player:self.video_player.stop();self.video_player.setSource(QUrl())
        self.track=track;self.video=video;self.seek=position;self.autoplay=autoplay
        if track.kind=='local':
            if not Path(track.uri).is_file():self.message.emit('음악 파일을 찾을 수 없습니다. 폴더 경로를 확인하세요.');return
            self.loading=False;self.player.setSource(QUrl.fromLocalFile(track.uri));self.player.play() if autoplay else self.player.pause();self.changed.emit();return
        self.loading=True;self.message.emit('유튜브 재생을 준비하고 있어요…');self.changed.emit()
        key=(track.key,video)
        cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<240:
            self.resolved(request,cached[1],'');return
        job=Job(request,resolve,track,video);self.jobs[request]=job
        job.signals.done.connect(self.resolved);self.pool.start(job)
    @Slot(int,object,str)
    def resolved(self,request,result,error):
        self.jobs.pop(request,None)
        if request!=self.request:return
        self.loading=False
        if error:self.message.emit(error);self.changed.emit();return
        self.cache[(self.track.key,self.video)]=(time.monotonic(),result)
        if len(self.cache)>8:self.cache.pop(next(iter(self.cache)))
        self.track.title=result['title']
        self.player.setSource(QUrl(result['url']))
        self.player.play() if self.autoplay else self.player.pause()
        if self.video:self.load_video(result.get('video_url'))
        self.message.emit('영상 스트림이 없는 곡입니다. 원본 영상 버튼을 이용해 주세요.' if self.video and not result['has_video'] else '재생 준비 완료')
        self.changed.emit()
    def set_video_output(self,widget):
        self.video_widget=widget
        if widget:
            if not self.video_player:
                self.video_player=QMediaPlayer(self)
                self.video_player.mediaStatusChanged.connect(self.video_status)
                self.video_player.errorOccurred.connect(lambda *_:self.message.emit('영상을 열지 못했습니다. 원본 영상 버튼으로 이어볼 수 있습니다.'))
                self.video_sync=QTimer(self);self.video_sync.setInterval(1000);self.video_sync.timeout.connect(self.sync_video)
            self.video_player.setVideoOutput(widget)
            if self.track and self.track.kind=='local':self.player.setVideoOutput(widget)
        else:
            self.player.setVideoOutput(None)
            if self.video_player:self.video_player.stop();self.video_player.setSource(QUrl());self.video_sync.stop()
    def load_video(self,url):
        if not self.video_player or not self.video_widget or not url:return
        self.video_player.setSource(QUrl(url));self.video_player.play();self.video_sync.start()
    def video_status(self,status):
        if status==QMediaPlayer.LoadedMedia:
            self.video_player.setPosition(self.player.position())
            self.video_player.play() if self.playing() else self.video_player.pause()
    def sync_video(self):
        if self.video_player and self.video and abs(self.video_player.position()-self.player.position())>700:
            self.video_player.setPosition(self.player.position())
    def play_state(self,state):
        if self.video_player and self.video:
            self.video_player.play() if state==QMediaPlayer.PlayingState else self.video_player.pause()
        self.changed.emit()
    def toggle(self):
        if self.loading:return
        if self.playing():self.player.pause()
        else:self.player.play()
    def stop(self):
        self.request+=1;self.loading=False;self.player.stop();self.player.setSource(QUrl());
        if self.video_player:self.video_player.stop();self.video_player.setSource(QUrl());self.video_sync.stop()
        self.track=None;self.changed.emit()
    def status(self,status):
        if status in (QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia) and self.seek:
            self.player.setPosition(self.seek);self.seek=0
        if status==QMediaPlayer.EndOfMedia:self.ended.emit()
    def error(self,*_):
        if self.track:self.message.emit('재생에 실패했습니다. 파일이나 유튜브 접근 상태를 확인해 주세요.')
    def set_visualizer(self,enabled):
        self.visual_enabled=enabled
        self.player.setAudioBufferOutput(self.capture if enabled else None)
    def buffer(self,buffer):
        if not self.visual_enabled:return
        now=time.monotonic()
        if now-self.last_buffer<.05 or not buffer.isValid():return
        self.last_buffer=now
        fmt=buffer.format(); types={QAudioFormat.Float:np.float32,QAudioFormat.Int16:np.int16,QAudioFormat.Int32:np.int32,QAudioFormat.UInt8:np.uint8}
        dtype=types.get(fmt.sampleFormat())
        if dtype is None:return
        samples=np.frombuffer(buffer.data(),dtype=dtype)
        channels=max(1,fmt.channelCount());samples=samples[::channels][-1024:].astype(np.float32)
        if len(samples)<64:return
        if dtype==np.uint8:samples=(samples-128)/128
        elif dtype!=np.float32:samples/=np.iinfo(dtype).max
        spectrum=np.abs(np.fft.rfft(samples*np.hanning(len(samples))))
        bands=np.array([np.max(x) if len(x) else 0 for x in np.array_split(spectrum[1:len(spectrum)//2],24)])
        bands=np.clip(np.log1p(bands)*.22,0,1)
        self.spectrum.emit(bands.tolist())
