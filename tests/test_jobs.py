import os,sys,time,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject,QThread,QThreadPool,Slot
from desktop_music_player.jobs import Job
class Receiver(QObject):
    def __init__(self):super().__init__();self.result=None;self.thread_seen=None
    @Slot(int,object,str)
    def done(self,ident,value,error):self.result=(ident,value,error);self.thread_seen=QThread.currentThread()
class WorkerTests(unittest.TestCase):
    def test_worker_result_returns_to_gui_thread(self):
        app=QApplication.instance() or QApplication([])
        receiver=Receiver();worker_threads=[]
        def work():worker_threads.append(QThread.currentThread());return ['found track']
        pool=QThreadPool();job=Job(7,work);job.signals.done.connect(receiver.done);pool.start(job)
        deadline=time.monotonic()+3
        while receiver.result is None and time.monotonic()<deadline:
            time.sleep(.01);app.processEvents()
        pool.waitForDone(1000)
        self.assertEqual(receiver.result,(7,['found track'],''))
        self.assertEqual(receiver.thread_seen,app.thread())
        self.assertNotEqual(worker_threads[0],app.thread())
if __name__=='__main__':unittest.main()
