# Third-party components

This project uses the following components. Consult their bundled notices and upstream licenses before redistributing a modified build.

- PySide6 / Qt: https://www.qt.io/qt-for-python — LGPL/GPL/commercial licensing; bundled Qt libraries are dynamically loaded.
- Qt Multimedia FFmpeg backend: https://doc.qt.io/qt-6/qtmultimedia-attribution-ffmpeg.html
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- yt-dlp-ejs: https://github.com/yt-dlp/ejs
- Deno: https://github.com/denoland/deno
- NumPy: https://numpy.org/
- Python: https://www.python.org/

- NAVER NanumSquareRound Regular / Bold: https://hangeul.naver.com/font — SIL Open Font License 1.1. Unmodified font files and the full NAVER license are bundled under assets/fonts. See docs/font-provenance.json for download sources and SHA-256 hashes.

Windows fallback fonts are referenced by name and are not included as files.

Claude Code and the MCP development bridge are design-time tools. Claude Code is not part of the music player distribution.

Full open-source license texts are included in licenses/. The MIT license of this application does not replace its dependencies' licenses.

Qt/PySide6 source and rebuild instructions: https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://code.qt.io/cgit/qt/ . The application uses external DLLs in _internal/PySide6 and _internal/shiboken6; users can replace those libraries with compatible modified builds. Application source and build scripts are provided in the public repository. Qt Multimedia's FFmpeg attribution and configuration are available at the URL above.
