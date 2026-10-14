"""Consistent, code-native 24px SVG icons; no font glyph placeholders."""
from functools import lru_cache
from PySide6.QtCore import Qt,QByteArray,QSize
from PySide6.QtGui import QPixmap,QPainter,QIcon
from PySide6.QtSvg import QSvgRenderer
PATHS={
'play':'<path d="m8 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
'pause':'<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>',
'previous':'<path d="M5 5v14m14-14L8 12l11 7Z"/>',
'next':'<path d="M19 5v14M5 5l11 7-11 7Z"/>',
'shuffle':'<path d="m18 14 4 4-4 4m0-20 4 4-4 4M2 4h3c5 0 9 14 14 14h3M2 20h3c2 0 4-3 5-5m4-6c2-3 3-3 5-3h3"/>',
'repeat':'<path d="m17 2 4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3"/>',
'repeat-one':'<path d="m17 2 4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3m8-8 2-1v6"/>',
'settings':'<path d="m9 3 1-1h4l1 1 .5 2 2 1 2-.5 1.5 2.5-1.5 1.5v3L21 14l-1.5 2.5-2-.5-2 1-.5 2-1 1h-4l-1-1-.5-2-2-1-2 .5L3 14l1.5-1.5v-3L3 8l1.5-2.5 2 .5 2-1Z"/><circle cx="12" cy="11" r="3"/>',
'pin':'<path d="m9 3 6 0-1 6 3 3v2H7v-2l3-3-1-6Zm3 11v7"/>',
'minimize':'<path d="M5 12h14"/>',
'close':'<path d="m6 6 12 12M6 18 18 6"/>',
'volume':'<path d="M11 4 6 8H3v8h3l5 4V4Zm4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
'random':'<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r=".8" fill="currentColor"/><circle cx="16" cy="8" r=".8" fill="currentColor"/><circle cx="12" cy="12" r=".8" fill="currentColor"/><circle cx="8" cy="16" r=".8" fill="currentColor"/><circle cx="16" cy="16" r=".8" fill="currentColor"/>',
'library':'<path d="M4 3v18M9 3v18m5-17 5-1 4 17-5 1Z"/>',
'queue':'<path d="M4 6h14M4 12h10M4 18h10m4-7 5 4-5 4Z"/>',
'playlist':'<path d="M3 5h13M3 10h13M3 15h8m8-7v10m0-10 3-1v9"/><ellipse cx="16" cy="18" rx="3" ry="2"/>',
'video':'<rect x="2" y="4" width="15" height="16" rx="3"/><path d="m17 9 5-3v12l-5-3Z"/>',
'folder':'<path d="M3 6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
'refresh':'<path d="M20 7v5h-5m5 0a8 8 0 1 0-2 6M20 7l-4-4"/>',
'search':'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
'plus':'<path d="M12 5v14M5 12h14"/>',
'list-plus':'<path d="M3 5h12M3 11h12M3 17h7m7-6v10m-5-5h10"/>',
'delete':'<path d="M3 6h18M9 6V3h6v3m-10 0 1 15h12l1-15M10 10v7m4-7v7"/>',
'clear':'<path d="M3 5h13M3 11h9M3 17h9m4-6 6 6m-6 0 6-6"/>',
'save':'<path d="M5 3h12l4 4v14H3V3Zm2 0v6h10V3M7 21v-8h10v8"/>',
'external':'<path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6"/>',
'download':'<path d="M12 3v12m-5-5 5 5 5-5M3 16v5h18v-5"/>',
'upload':'<path d="M12 16V4m-5 5 5-5 5 5M3 16v5h18v-5"/>',
'expand':'<path d="m6 9 6 6 6-6"/>',
'music':'<path d="M9 18V4l12-2v14M9 7l12-2"/><ellipse cx="6" cy="18" rx="3" ry="3"/><ellipse cx="18" cy="16" rx="3" ry="3"/>',
'youtube':'<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3Z" fill="currentColor" stroke="none"/>',
}
@lru_cache(maxsize=160)
def icon(name,color='#5B6B7A'):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{PATHS.get(name,PATHS["music"]).replace("currentColor",color)}</svg>'
    renderer=QSvgRenderer(QByteArray(svg.encode()));pix=QPixmap(48,48);pix.fill(Qt.transparent);p=QPainter(pix);renderer.render(p);p.end();pix.setDevicePixelRatio(2);return QIcon(pix)
