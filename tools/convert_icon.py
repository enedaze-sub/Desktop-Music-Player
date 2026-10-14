"""Deterministic PNG to Windows ICO format conversion; preserves image alpha."""
import struct,sys
from pathlib import Path
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt
ROOT=Path(__file__).resolve().parents[1]
image=QImage(str(ROOT/'assets'/'app-icon.png'))
assert not image.isNull()
entries=[];payload=[];sizes=(16,20,24,32,40,48,64,128,256);offset=6+16*len(sizes)
for size in sizes:
 img=image.scaled(size,size,Qt.IgnoreAspectRatio,Qt.SmoothTransformation).convertToFormat(QImage.Format_ARGB32)
 # ICO DIB: bottom-up BGRA pixels, followed by a padded transparency AND mask.
 stride=((size+31)//32)*4;pixels=bytearray();mask=bytearray()
 for y in range(size-1,-1,-1):
  row=bytearray(stride)
  for x in range(size):
   c=img.pixelColor(x,y);pixels.extend((c.blue(),c.green(),c.red(),c.alpha()))
   if c.alpha()==0:row[x//8]|=1<<(7-x%8)
  mask.extend(row)
 data=struct.pack('<IiiHHIIiiII',40,size,size*2,1,32,0,len(pixels)+len(mask),0,0,0,0)+pixels+mask
 entries.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset));payload.append(data);offset+=len(data)
(ROOT/'assets'/'app.ico').write_bytes(struct.pack('<HHH',0,1,len(sizes))+b''.join(entries)+b''.join(payload))
print('ICO sizes:',sizes)
