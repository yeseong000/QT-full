/**
 * 주만나 AI 큐티 - 공통 유틸
 */

// 테마별 모바일 브라우저 chrome 색 (--bg-paper와 일치)
const THEME_CHROME_COLORS = {
  default: '#F0F4F2',
  dark:    '#1A1D1B',
};

/**
 * 테마 적용: data-theme 속성 + 모바일 브라우저 주소창 색 + iOS 상태바 스타일을 한 번에 동기화.
 * 페이지 초기 로드 시(IIFE)와 사용자가 테마 모달에서 변경 시 동일하게 호출.
 */
function applyTheme(theme) {
  const t = (theme && THEME_CHROME_COLORS[theme]) ? theme : 'default';

  // 1) data-theme 속성
  if (t === 'default') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', t);
  }

  // 2) 모바일 브라우저 주소창 색
  // index.html처럼 시간대별 색을 자체 관리하는 페이지(html[data-uses-time-slot])는 건드리지 않음
  if (!document.documentElement.hasAttribute('data-uses-time-slot')) {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', THEME_CHROME_COLORS[t]);
  }

  // 3) iOS PWA 상태바 스타일 (다크일 때 노치 영역도 어둡게)
  const iosBar = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
  if (iosBar) iosBar.setAttribute('content', t === 'dark' ? 'black-translucent' : 'default');
}

// PWA standalone 모드 감지 — iOS Safari는 @media (display-mode: standalone) 미디어쿼리가
// false를 반환하는 경우가 있어 navigator.standalone과 OR로 체크.
// 매치되면 html.is-pwa 클래스 부착 → CSS는 이 클래스 선택자로 PWA 전용 규칙 매칭(미디어쿼리 우회).
(function detectPWA() {
  var mqMatches = window.matchMedia && window.matchMedia('(display-mode: standalone)').matches;
  var iosStandalone = navigator.standalone === true;
  if (mqMatches || iosStandalone) document.documentElement.classList.add('is-pwa');
})();

// 폰트 크기 즉시 적용
(function applyStoredFontSize() {
  try {
    const size = localStorage.getItem('settings.fontSize');
    if (size) document.documentElement.setAttribute('data-font-size', size);
  } catch(e) {}
})();

// 폰트 스타일 즉시 적용 (기본: 기본=Pretendard 산세리프. 세리프는 사용자가 직접 선택 시에만)
(function applyStoredFontStyle() {
  try {
    const style = localStorage.getItem('settings.fontStyle') || 'pretendard';
    if (style !== 'pretendard') {
      document.documentElement.setAttribute('data-font-style', style);
    }
  } catch(e) {
    document.documentElement.removeAttribute('data-font-style');
  }
})();

// iOS PWA standalone 모드의 viewport height 버그 보정:
// 첫 렌더 시 100dvh가 ~10px 빗나가 하단 영역이 위로 떠 보이는 문제.
// window.innerHeight를 --app-height에 동기화 → common.css의 @media (display-mode: standalone)
// 안에서 .app-container { height: var(--app-height, 100dvh) }로 사용.
// 즉시 + rAF + 100ms + 300ms 시점에 반복 호출 → iOS가 viewport를 안정화하는 타이밍 따라잡기.
(function setupAppHeight() {
  function setAppHeight() {
    document.documentElement.style.setProperty('--app-height', window.innerHeight + 'px');
  }
  setAppHeight();
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(setAppHeight);
  setTimeout(setAppHeight, 100);
  setTimeout(setAppHeight, 300);
  window.addEventListener('resize', setAppHeight);
  window.addEventListener('orientationchange', setAppHeight);
})();

// ── 시간대 임시 전환 (sessionStorage, 영구 저장 X) ──────────────────────
// 홈의 버튼을 탭하면 "다음 시간대"를 sessionStorage('settings.timeSlot')에 저장.
// 값이 있으면 "현재 시각" 대신 그 시간대를 앱 전체(STEP·달력 등)가 따른다(세션 공통 단일 출처).
// sessionStorage라 탭을 닫고 새로 접속하면 사라지고 → 다시 현재 시각 기준으로 계산된다.
const TIME_SLOTS = ['dawn', 'morning', 'afternoon', 'evening', 'night'];
function getSlotOverride() {
  try {
    const v = sessionStorage.getItem('settings.timeSlot');
    return (v && TIME_SLOTS.indexOf(v) >= 0) ? v : null;
  } catch (e) {
    return null;
  }
}

// 시간대(5단계) — 오버라이드가 있으면 그걸, 없으면 현재 시각 기준.
//   홈 화면(index.html)과 동일한 경계. 주위 배경(ambient) 그라데이션을 고르는 데 쓴다.
function pickTimeSlot(date = new Date()) {
  const ov = getSlotOverride();
  if (ov) return ov;
  const h = date.getHours();
  if (h >= 4  && h < 7)  return 'dawn';
  if (h >= 7  && h < 12) return 'morning';
  if (h >= 12 && h < 17) return 'afternoon';
  if (h >= 17 && h < 22) return 'evening';
  return 'night';
}

// 시간대 기반 자동 배경(다크/라이트) — 어두운 시간대(밤)만 dark.
// (새벽은 실제 일러스트가 밝은 파스텔이라 라이트로 둔다 — 저녁과 동일한 처리)
// pickTimeSlot이 오버라이드를 반영하므로 수동 선택 시에도 다크/라이트가 함께 따라간다.
function pickAutoTheme(date = new Date()) {
  const slot = pickTimeSlot(date);
  return (slot === 'night') ? 'dark' : 'default';
}

// 시간대별 "주위 배경(ambient)" — 홈 화면 5색 팔레트(SKY/GROUND)를 연하게 풀어낸
// 2-stop 그라데이션 [위(하늘쪽), 아래(바닥쪽)]. iOS의 은은한 환경광 느낌.
//   - 밝은 시간대(새벽·아침·오후·저녁): 채도를 낮춘 밝은 파스텔 → 카드가 또렷이 떠 보임
//   - 어두운 시간대(밤): 카드(다크 테마)와 자연스레 어울리는 깊은 톤
// 배경은 2단계로 분리한다 (카드는 그림자로 떠 있으므로 색 대비에 의존하지 않음):
//   ① 본문 배경(INNER): 카드가 얹히는 안쪽 — 시간대 색을 "적당히" 살린 톤
//   ② 바깥 배경(OUTER): PC 프레임 여백 — 본문보다 "훨씬 더 연하게" (거의 화이트에 살짝)
// 어두운 시간대(밤)는 다크 카드 대비를 위해 깊은 톤 유지(바깥은 살짝 더 깊게).
// 본문 배경은 3색(하늘·바닥·accent)으로 — 흐린 사진처럼 다중 색이 고이게 한다.
// 글래스 카드가 위에서 비추므로 채도를 살짝 높여(=비쳤을 때 색이 살아남) 둔다.
const AMBIENT_INNER = {
  dawn:      ['#CBBAD7', '#EBD4C1', '#DCC0CC'],  // 여명: 부드러운 라벤더 → 복숭아빛 햇무리 → 먼지빛 로즈 (밝은 파스텔)
  morning:   ['#FCEFC4', '#F8EDCC', '#FBE6A8'],  // 아침: 밝은 노랑 → 크림 → 햇살 골드 (저녁과 구분)
  afternoon: ['#DEE9F3', '#F1E7D3', '#D4E2F0'],  // 오후: 맑은 하늘빛 → 따뜻한 모래
  evening:   ['#F5D7BD', '#FADCA4', '#F1C7AC'],  // 저녁: 노을 살구 → 금빛
  night:     ['#0C1428', '#18223A', '#15305A'],  // 밤: 깊은 네이비 (다크)
};
const AMBIENT_OUTER = {
  dawn:      ['#F3EDF2', '#F6EFEA'],  // 여명: 본문보다 훨씬 연하게 (밝은 파스텔)
  morning:   ['#FBF5EF', '#FAF7F0'],  // 아침: 본문보다 훨씬 연하게
  afternoon: ['#F2F5F9', '#F8F5EE'],  // 오후: 본문보다 훨씬 연하게
  evening:   ['#FAF2EB', '#FCF6E9'],  // 저녁: 본문보다 훨씬 연하게
  night:     ['#080F1E', '#101A30'],  // 밤(다크): 본문보다 더 깊게
};

function applyAmbient(date = new Date()) {
  const slot = pickTimeSlot(date);
  const inner = AMBIENT_INNER[slot] || AMBIENT_INNER.afternoon;
  const outer = AMBIENT_OUTER[slot] || AMBIENT_OUTER.afternoon;
  const root = document.documentElement;
  root.style.setProperty('--ambient-1', inner[0]);          // 본문 배경 (하늘)
  root.style.setProperty('--ambient-2', inner[1]);          // 본문 배경 (바닥)
  root.style.setProperty('--ambient-3', inner[2] || inner[0]); // 본문 배경 (accent)
  root.style.setProperty('--ambient-bg-1', outer[0]);       // 바깥 배경
  root.style.setProperty('--ambient-bg-2', outer[1]);
}

function applyAutoTheme() {
  applyTheme(pickAutoTheme());
  applyAmbient();
}

// 즉시 적용 (DOMContentLoaded 전 → 플래시 최소화)
applyAutoTheme();

// 페이지가 떠 있는 동안 시간 경계(07:00 / 22:00)에서 자동 전환
if (typeof window !== 'undefined') {
  setInterval(applyAutoTheme, 60 * 60 * 1000);   // 1시간마다
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) applyAutoTheme();
  });
}

// 과거 사용자가 수동으로 저장해둔 값 정리(있으면 제거)
// settings.timeSlot은 이제 sessionStorage만 사용 → 예전 영구 저장본(localStorage)은 제거
try { localStorage.removeItem('settings.background'); } catch (e) {}
try { localStorage.removeItem('settings.timeSlot'); } catch (e) {}

function applyFontStyle(style) {
  const s = style || Storage.get('settings.fontStyle', 'pretendard') || 'pretendard';
  if (s === 'pretendard') {
    document.documentElement.removeAttribute('data-font-style');
  } else {
    document.documentElement.setAttribute('data-font-style', s);
  }
}

const Common = {
  applyTheme,
  applyAutoTheme,
  pickAutoTheme,
  pickTimeSlot,
  getSlotOverride,
  applyAmbient,
  applyFontStyle,

  /**
   * 닉네임 정규화 — 끝에 '님'이 붙어 있으면 떼고 반환. ('님'은 호칭이라 신원의 일부 X)
   * 함수 이름은 호환을 위해 유지하지만 실제로는 호칭을 부착하지 않는다.
   */
  withHonorific(name) {
    if (!name) return '어린양';
    let s = String(name).trim();
    while (s.endsWith('님')) s = s.slice(0, -1).trim();
    return s || '어린양';
  },

  /**
   * 시간대별 인사말 — 호칭(님)은 부착하지 않는다.
   */
  getGreeting(name = '어린양') {
    const hour = new Date().getHours();
    let base;

    if (hour >= 4 && hour < 7) {
      base = '이른 아침이네요';
    } else if (hour >= 7 && hour < 12) {
      base = '좋은 아침이에요';
    } else if (hour >= 12 && hour < 18) {
      base = '평안한 오후예요';
    } else if (hour >= 18 && hour < 23) {
      base = '편안한 저녁이에요';
    } else {
      base = '고요한 밤이네요';
    }

    return `${base}, ${this.withHonorific(name)}`;
  },

  /**
   * 시간대 이모지
   */
  getTimeEmoji() {
    const hour = new Date().getHours();
    if (hour >= 4 && hour < 7) return '🌌';
    if (hour >= 7 && hour < 12) return '☀️';
    if (hour >= 12 && hour < 18) return '🌤️';
    if (hour >= 18 && hour < 23) return '🌙';
    return '🌃';
  },

  /**
   * 오늘 날짜 (YYYY-MM-DD)
   */
  todayISO() {
    return new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Seoul' });
  },

  /**
   * 한글 날짜 포맷 (2026년 4월 22일 수요일)
   */
  formatKoreanDate(date = new Date()) {
    const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
    const y = date.getFullYear();
    const m = date.getMonth() + 1;
    const d = date.getDate();
    const w = weekdays[date.getDay()];
    return `${y}년 ${m}월 ${d}일 ${w}요일`;
  },

  /**
   * JSON 파일 로드
   */
  async loadJSON(path) {
    try {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (e) {
      console.error('loadJSON error:', path, e);
      return null;
    }
  },

  /**
   * iOS overlay 느낌의 자동 숨김 스크롤바.
   * 스크롤 중에만 is-scrolling 클래스를 붙이고, 멈춘 뒤 timeout ms 후 제거.
   * CSS에서 .is-scrolling 클래스에 스크롤바 색을 넣어두면 자동으로 보임/숨김 처리됨.
   */
  setupAutoHideScroll(element, timeout = 1500) {
    if (!element) return;
    let t;
    element.addEventListener('scroll', () => {
      element.classList.add('is-scrolling');
      clearTimeout(t);
      t = setTimeout(() => {
        element.classList.remove('is-scrolling');
      }, timeout);
    }, { passive: true });
  },
};

// 자동 연결: 스크롤 가능한 주요 컨테이너들에 auto-hide 적용
if (typeof window !== 'undefined') {
  window.Common = Common;
  document.addEventListener('DOMContentLoaded', () => {
    ['.app-scroll', '.scripture-toggle__body'].forEach(sel => {
      document.querySelectorAll(sel).forEach(el => Common.setupAutoHideScroll(el));
    });
  });
}

// ───────────────────────────────────────────────────────────────────────────
// Service Worker 등록 — iOS PWA snapshot 캐시 우회 (network-first 전략)
//
// 왜: iOS Safari PWA가 홈 아이콘 launch 시 옛 HTML/CSS/JS를 끈질기게 캐시(WebKit #199110).
//     SW가 모든 fetch를 가로채 항상 네트워크 우선 → 새 배포 자동 반영.
// 어떻게: '/sw.js' 등록 → 첫 방문엔 일반 HTTP, 두 번째 방문부터 SW 제어.
// 한 번 설치되면 사용자 추가 행동 없이 영구 작동.
// ───────────────────────────────────────────────────────────────────────────
if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((reg) => {
        // 1시간마다 SW 업데이트 체크 (새 SW가 origin에 있으면 background install)
        setInterval(() => { reg.update().catch(() => {}); }, 60 * 60 * 1000);
      })
      .catch((err) => { /* SW 등록 실패해도 앱은 정상 동작 */ });
  });
}
