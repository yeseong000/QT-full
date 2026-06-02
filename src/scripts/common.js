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

// 폰트 크기 즉시 적용
(function applyStoredFontSize() {
  try {
    const size = localStorage.getItem('settings.fontSize');
    if (size) document.documentElement.setAttribute('data-font-size', size);
  } catch(e) {}
})();

// 폰트 스타일 즉시 적용 (기본: 세리프)
(function applyStoredFontStyle() {
  try {
    const style = localStorage.getItem('settings.fontStyle') || 'noto-serif';
    if (style !== 'pretendard') {
      document.documentElement.setAttribute('data-font-style', style);
    }
  } catch(e) {
    document.documentElement.setAttribute('data-font-style', 'noto-serif');
  }
})();

// 시간대 기반 자동 배경
//   22:00–07:00 → dark, 그 외 → default(light)
function pickAutoTheme(date = new Date()) {
  const h = date.getHours();
  return (h >= 22 || h < 7) ? 'dark' : 'default';
}

// 시간대(5단계) — 홈 화면(index.html)과 동일한 경계.
// 주위 배경(ambient) 그라데이션을 고르는 데 쓴다.
function pickTimeSlot(date = new Date()) {
  const h = date.getHours();
  if (h >= 4  && h < 7)  return 'dawn';
  if (h >= 7  && h < 12) return 'morning';
  if (h >= 12 && h < 17) return 'afternoon';
  if (h >= 17 && h < 22) return 'evening';
  return 'night';
}

// 시간대별 "주위 배경(ambient)" — 홈 화면 5색 팔레트(SKY/GROUND)를 연하게 풀어낸
// 2-stop 그라데이션 [위(하늘쪽), 아래(바닥쪽)]. iOS의 은은한 환경광 느낌.
//   - 낮 시간대(morning·afternoon·evening): 채도를 낮춘 밝은 파스텔 → 카드가 또렷이 떠 보임
//   - 어두운 시간대(dawn·night): 카드(다크 테마)와 자연스레 어울리는 깊은 톤
// 배경은 2단계로 분리한다 (카드는 그림자로 떠 있으므로 색 대비에 의존하지 않음):
//   ① 본문 배경(INNER): 카드가 얹히는 안쪽 — 시간대 색을 "적당히" 살린 톤
//   ② 바깥 배경(OUTER): PC 프레임 여백 — 본문보다 "훨씬 더 연하게" (거의 화이트에 살짝)
// 어두운 시간대(dawn·night)는 다크 카드 대비를 위해 깊은 톤 유지(바깥은 살짝 더 깊게).
// 본문 배경은 3색(하늘·바닥·accent)으로 — 흐린 사진처럼 다중 색이 고이게 한다.
// 글래스 카드가 위에서 비추므로 채도를 살짝 높여(=비쳤을 때 색이 살아남) 둔다.
const AMBIENT_INNER = {
  dawn:      ['#22223C', '#2C2945', '#383152'],  // 여명: 깊은 남보라 (다크)
  morning:   ['#F9E1CF', '#F4EACB', '#FBD9C2'],  // 아침: 또렷한 살구 → 크림
  afternoon: ['#DEE9F3', '#F1E7D3', '#D4E2F0'],  // 오후: 맑은 하늘빛 → 따뜻한 모래
  evening:   ['#F5D7BD', '#FADCA4', '#F1C7AC'],  // 저녁: 노을 살구 → 금빛
  night:     ['#0C1428', '#18223A', '#15305A'],  // 밤: 깊은 네이비 (다크)
};
const AMBIENT_OUTER = {
  dawn:      ['#14141F', '#1B1B2B'],  // 여명(다크): 본문보다 더 깊게 → 프레임이 떠 보임
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

// 과거 사용자가 수동으로 저장해둔 background 값 정리(있으면 제거)
try { localStorage.removeItem('settings.background'); } catch (e) {}

function applyFontStyle(style) {
  const s = style || Storage.get('settings.fontStyle', 'noto-serif') || 'noto-serif';
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
