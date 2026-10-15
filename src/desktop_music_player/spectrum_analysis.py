"""Small, cached FFT analysis; affects drawing only, never playback gain."""
import numpy as np
class SpectrumAnalyzer:
    def __init__(self):self.signature=None;self.reference=.015
    def analyze(self,samples,rate):
        size=len(samples)
        if size<64 or rate<=0:return [0.]*24
        signature=(size,rate)
        if signature!=self.signature:
            self.signature=signature;self.window=np.hanning(size);self.normalizer=max(1.,self.window.sum()/2)
            edges=np.geomspace(40,min(16000,rate*.49),25);freqs=np.fft.rfftfreq(size,1/rate)
            self.ranges=[(max(1,int(np.searchsorted(freqs,a))),max(2,int(np.searchsorted(freqs,b)))) for a,b in zip(edges[:-1],edges[1:])]
            self.weights=(np.sqrt(edges[:-1]*edges[1:])/200)**.22
        if float(np.max(np.abs(samples)))<.0001:return [0.]*24
        spectrum=np.abs(np.fft.rfft(samples*self.window))/self.normalizer
        bands=np.array([float(np.max(spectrum[a:max(a+1,b)])) if a<len(spectrum) else 0. for a,b in self.ranges])*self.weights
        self.reference=max(.015,float(bands.max()),self.reference*.97)
        return np.clip(bands/self.reference,0,1).__pow__(.58).tolist()
