# 테마 JSON

assets/theme-presets.json은 두 개의 실제 예시입니다. 최상위 format은 desktop-music-player-themes, version은 1, themes는 한 개 이상의 테마 배열입니다.

테마에는 name(1~60자), colors(7개 #RRGGBB 색), gradients(bg/panel/accent/spectrum의 enabled·end·direction), visualizer(enabled·style)가 들어갑니다. direction은 horizontal/vertical/diagonal, style은 bars/led/mirror/line/glow입니다. 이전 6색 데이터에서 spectrum이 빠졌다면 accent를 이어받습니다.

파일은 UTF-8 JSON이며 불러올 때 4MB까지 지원합니다. 전체 파일 검증을 통과한 뒤 한 번에 목록에 추가합니다. 이름 충돌은 (2), (3)으로 새 항목을 만들며 내보내기에는 지정된 테마 필드만 기록합니다. 사용자 저장 목록은 data/player.sqlite3 안에 있으며 Git과 배포 ZIP에서 제외합니다.

기본 6종은 themes.json에서 제공하며 저장 목록과 분리됩니다. assets/theme-presets.json은 JSON 교환 예시이며 새 저장 목록을 자동으로 채우지 않습니다.
