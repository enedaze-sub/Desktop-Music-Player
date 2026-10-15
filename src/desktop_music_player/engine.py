"""Audio owns the playback clock; video is a detachable, muted companion."""
import logging
import re
import time
from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject, QUrl, Signal, Slot, QThreadPool, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioBufferOutput, QAudioFormat, QVideoFrame
from .jobs import Job
from .youtube import resolve
from .core import VIDEO

log = logging.getLogger('player.media')


def safe_error(text):
    return re.sub(r'https?://[^\s\"\']+', '[stream URL]', str(text))[:400]


class Engine(QObject):
    message = Signal(str)
    changed = Signal()
    ended = Signal()
    spectrum = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.3)
        self.player.setAudioOutput(self.audio)
        self.capture = QAudioBufferOutput(self)
        self.capture.audioBufferReceived.connect(self.buffer)
        self.player.playbackStateChanged.connect(self.play_state)
        self.player.durationChanged.connect(lambda _: self.changed.emit())
        self.player.positionChanged.connect(self.remember_position)
        self.player.mediaStatusChanged.connect(self.status)
        self.player.errorOccurred.connect(self.error)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.track = None
        self.video = False
        self.video_visible = True
        self.video_widget = None
        self.video_player = None
        self.loading = False
        self.request = 0
        self.video_request = 0
        self.job_sequence = 0
        self.jobs = {}
        self.cache = {}
        self.current_stream = None
        self.seek = 0
        self.last_position = 0
        self.autoplay = True
        self.retry_count = 0
        self.video_retry_count = 0
        self._changing_source = False
        self._changing_video = False
        self.last_buffer = 0
        self.visual_enabled = False
        self.video_sync = QTimer(self)
        self.video_sync.setInterval(1000)
        self.video_sync.timeout.connect(self.sync_video)

    def playing(self):
        return self.player.playbackState() == QMediaPlayer.PlayingState

    def cached_stream(self):
        cached = self.cache.get(self.track.key) if self.track else None
        return cached[1] if cached and cached[0] > time.monotonic() else None

    def cache_stream(self, result):
        ttl = 180
        if result.get('expires_at') is not None:
            ttl = max(0, min(ttl, result['expires_at'] - time.time() - 30))
        self.cache[self.track.key] = (time.monotonic() + ttl, result)
        if len(self.cache) > 8:
            self.cache.pop(next(iter(self.cache)))

    def play_track(self, track, video=False, position=0, autoplay=True):
        self.request += 1
        self._changing_source = True
        self.player.stop()
        self.player.setSource(QUrl())
        self._changing_source = False
        self.clear_video()
        self.track = track
        self.video = video
        self.seek = self.last_position = position
        self.autoplay = autoplay
        self.retry_count = self.video_retry_count = 0
        self.current_stream = None
        if track.kind == 'local':
            self.loading = False
            if not Path(track.uri).is_file():
                self.message.emit('음악 파일을 찾을 수 없습니다. 폴더 경로를 확인하세요.')
                self.changed.emit()
                return
            self.player.setVideoSink(None)
            self.set_audio_source(QUrl.fromLocalFile(track.uri))
            if video and self.video_visible:self.load_local_video()
            self.changed.emit()
            return
        self.player.setVideoSink(None)
        cached = self.cached_stream()
        if cached:
            self.apply_audio(cached)
        else:
            self.request_audio()

    def submit_stream(self, kind, fallback=False):
        self.job_sequence += 1
        ident = self.job_sequence
        job = Job(ident, resolve, self.track, kind == 'video', fallback)
        self.jobs[ident] = (job, self.request, kind, self.video_request)
        job.signals.done.connect(self.resolved)
        self.pool.start(job)

    def request_audio(self):
        self.loading = True
        self.message.emit('유튜브 연결을 다시 여는 중이에요…' if self.retry_count else '유튜브 재생을 준비하고 있어요…')
        self.changed.emit()
        self.submit_stream('audio', fallback=bool(self.retry_count))

    @Slot(int, object, str)
    def resolved(self, ident, result, error):
        pending = self.jobs.pop(ident, None)
        if not pending or pending[1] != self.request or self.track is None:
            return
        kind = pending[2]
        if kind == 'video' and (pending[3] != self.video_request or not self.video or not self.video_visible):
            return
        if error:
            log.warning('%s extraction failed: %s', kind, safe_error(error))
            if kind == 'audio':
                self.recover_audio()
            else:
                self.video_failed()
            return
        self.cache_stream(result)
        self.current_stream = result
        if kind == 'audio':
            self.apply_audio(result)
        else:
            self.load_video(result.get('video_fallback_url') or result.get('video_url'))

    def set_audio_source(self, url):
        self._changing_source = True
        self.player.setSource(url)
        self._changing_source = False
        self.player.play() if self.autoplay else self.player.pause()
        if self.player.error()!=QMediaPlayer.NoError:
            request=self.request
            QTimer.singleShot(0,lambda:self.error(self.player.error(),self.player.errorString()) if request==self.request else None)

    def apply_audio(self, result):
        self.loading = False
        self.current_stream = result
        self.track.title = result['title']
        self.set_audio_source(QUrl(result['url']))
        if self.video and self.video_visible:
            self.load_video(result.get('video_url'))
        if self.player.error()==QMediaPlayer.NoError:self.message.emit('재생 준비 완료')
        self.changed.emit()

    def recover_audio(self):
        if not self.track:
            return
        if self.track.kind == 'youtube' and self.retry_count < 1:
            self.retry_count += 1
            self.seek = self.last_position
            self.cache.pop(self.track.key, None)
            self.clear_video()
            self.loading = True
            self._changing_source = True
            self.player.stop()
            self.player.setSource(QUrl())
            self._changing_source = False
            request = self.request
            QTimer.singleShot(150, lambda: self.request_audio() if request == self.request and self.track else None)
            self.message.emit('유튜브 연결을 다시 여는 중이에요…')
        else:
            self.loading = False
            self.message.emit('재생 연결을 복구하지 못했습니다. 다시 재생하거나 다른 곡을 골라 주세요.')
        self.changed.emit()

    @Slot(QMediaPlayer.Error, str)
    def error(self, error, text):
        if self._changing_source or not self.track or error == QMediaPlayer.NoError:
            return
        if self.player.error() == QMediaPlayer.NoError:
            return  # an old source's queued error was superseded by a source change
        log.warning('Audio error: %s; format=%s; retry=%s; detail=%s', error.name,
                    (self.current_stream or {}).get('audio_format', ''), self.retry_count, safe_error(text))
        if not self.loading:
            self.recover_audio()

    def set_video_output(self, widget):
        self.set_video_mode(widget is not None, widget)

    def set_video_mode(self, enabled, widget=None):
        new_widget=widget is not None and widget is not self.video_widget
        if widget is not None:
            self.video_widget = widget
        if self.video == enabled and not new_widget:
            return
        self.video = enabled
        self.video_retry_count = 0
        self.clear_video()
        if not enabled or not self.track or not self.video_visible:
            return
        if self.track.kind == 'local':
            self.load_local_video()
            return
        if self.loading:
            self.video_widget.set_message('곡 준비가 끝나면 영상이 표시됩니다.')
            return
        cached = self.cached_stream()
        if cached:
            self.current_stream = cached
            self.load_video(cached.get('video_url'))
        else:
            self.video_widget.set_message('영상을 준비하고 있어요…')
            self.submit_stream('video')

    def load_local_video(self):
        if not self.video_widget:return
        if Path(self.track.uri).suffix.lower() in VIDEO:self.load_video(QUrl.fromLocalFile(self.track.uri))
        else:self.video_widget.set_message('현재 곡은 오디오 파일입니다.')

    def set_video_visible(self, visible):
        if self.video_visible == visible:
            return
        self.video_visible = visible
        if not visible:
            self.clear_video()
        elif self.video:
            self.video = False
            self.set_video_mode(True, self.video_widget)

    def clear_video(self):
        self.video_request += 1
        self.video_sync.stop()
        self.player.setVideoSink(None)
        if self.video_player:
            self._changing_video = True
            self.video_player.stop()
            self.video_player.setSource(QUrl())
            self._changing_video = False
        if self.video_widget:
            self.video_widget.set_message('영상을 준비하고 있어요…')

    def ensure_video_player(self):
        if self.video_player is None:
            self.video_player = QMediaPlayer(self)
            self.video_audio = QAudioOutput(self)
            self.video_audio.setMuted(True)
            self.video_audio.setVolume(0)
            self.video_player.setAudioOutput(self.video_audio)
            self.video_player.mediaStatusChanged.connect(self.video_status)
            self.video_player.errorOccurred.connect(self.video_error)
            self.video_widget.videoSink().videoFrameChanged.connect(self.video_frame)
        self.video_player.setVideoSink(self.video_widget.videoSink())

    def load_video(self, url):
        if not self.video or not self.video_visible or not self.video_widget:
            return
        if not url:
            self.video_widget.set_message('이 곡의 영상 스트림을 찾지 못했습니다.')
            return
        self.ensure_video_player()
        self.video_widget.set_message('영상을 여는 중이에요…')
        self._changing_video = True
        self.video_player.setSource(QUrl(url))
        self._changing_video = False
        # Decode a first frame even when the main audio is paused.
        self.video_player.play()
        self.video_sync.start()
        if self.video_player.error()!=QMediaPlayer.NoError:
            request=self.video_request
            QTimer.singleShot(0,lambda:self.video_error(self.video_player.error(),self.video_player.errorString()) if request==self.video_request else None)

    def video_status(self, status):
        if status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia) and self.video_player and self.video:
            if abs(self.video_player.position() - self.player.position()) > 350:
                self.video_player.setPosition(self.player.position())

    @Slot(QVideoFrame)
    def video_frame(self, frame):
        if frame.isValid() and self.video and not self.playing() and self.video_player:
            self.video_player.pause()

    @Slot(QMediaPlayer.Error, str)
    def video_error(self, error, text):
        if self._changing_video or not self.video or not self.video_visible or error == QMediaPlayer.NoError:
            return
        log.warning('Video error: %s; retry=%s; detail=%s', error.name, self.video_retry_count, safe_error(text))
        if self.track and self.track.kind=='local':
            self.video_failed();return
        if self.video_retry_count < 1:
            self.video_retry_count += 1
            request, video_request = self.request, self.video_request
            def retry():
                if request != self.request or video_request != self.video_request or not self.video:
                    return
                alternate = (self.current_stream or {}).get('video_fallback_url')
                if alternate:
                    self.load_video(alternate)
                else:
                    self.submit_stream('video', fallback=True)
            QTimer.singleShot(150, retry)
        else:
            self.video_failed()

    def video_failed(self):
        self.video_sync.stop()
        if self.video_widget:
            self.video_widget.set_message('이 영상 형식을 표시하지 못했습니다. 오디오 재생은 계속됩니다.' if self.track and self.track.kind=='local' else '영상 연결을 열지 못했습니다. 영상 탭을 닫았다가 다시 열어 주세요.')
        self.message.emit('영상 연결이 제한되었습니다. 오디오 재생은 계속됩니다.')

    def sync_video(self):
        if self.video_player and self.video and self.video_visible and not self.video_player.source().isEmpty():
            if abs(self.video_player.position() - self.player.position()) > 350:
                self.video_player.setPosition(self.player.position())

    def remember_position(self, position):
        if not self._changing_source and not self.loading and self.player.error() == QMediaPlayer.NoError:
            self.last_position = position

    def seek_to(self, position):
        position = max(0, min(position, self.player.duration()))
        self.last_position = position
        self.player.setPosition(position)
        if self.video_player and self.video and not self.video_player.source().isEmpty():
            self.video_player.setPosition(position)

    def play_state(self, state):
        if not self._changing_source and not self.loading:
            if state == QMediaPlayer.PlayingState:
                self.autoplay = True
            elif state == QMediaPlayer.PausedState:
                self.autoplay = False
        if self.video_player and self.video and not self.video_player.source().isEmpty():
            self.video_player.play() if state == QMediaPlayer.PlayingState else self.video_player.pause()
        self.changed.emit()

    def toggle(self):
        if self.loading:
            self.autoplay = not self.autoplay
            self.changed.emit()
            return
        if self.player.error() != QMediaPlayer.NoError and self.track:
            self.play_track(self.track, self.video, self.last_position)
        elif self.playing():
            self.autoplay = False
            self.player.pause()
        else:
            self.autoplay = True
            if self.player.mediaStatus() == QMediaPlayer.EndOfMedia:
                self.seek_to(0)
            self.player.play()

    def stop(self):
        self.request += 1
        self.loading = False
        self.track = None
        self._changing_source = True
        self.player.stop()
        self.player.setSource(QUrl())
        self._changing_source = False
        self.clear_video()
        self.last_position = self.seek = 0
        self.changed.emit()

    def status(self, status):
        if self._changing_source:
            return
        if status==QMediaPlayer.LoadedMedia and self.track and self.track.kind=='local':self.player.setActiveVideoTrack(-1)
        if status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia) and self.seek:
            self.seek_to(self.seek)
            self.seek = 0
        if status == QMediaPlayer.EndOfMedia and not self.loading:
            self.ended.emit()

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
