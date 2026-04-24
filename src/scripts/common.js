/**
 * 주만나 AI 큐티 - 공통 유틸
 */

// 테마별 모바일 브라우저 chrome 색 (--bg-paper와 일치)
const THEME_CHROME_COLORS = {
  default: '#F0F4F2',
  rose:    '#FCF3EE',
  dark:    '#1A231D',
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
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', THEME_CHROME_COLORS[t]);

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

// 테마 즉시 적용 (DOMContentLoaded 전에 실행 → 플래시 최소화)
(function applyStoredTheme() {
  let stored = null;
  try {
    const raw = localStorage.getItem('settings.background');
    if (raw) stored = raw;
  } catch (e) { /* localStorage 차단/private 모드: 무시 */ }

  // 사용자가 명시적으로 고른 값이 있으면 우선,
  // 없으면 OS의 prefers-color-scheme를 따라감
  if (!stored && window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches) {
    stored = 'dark';
  }

  applyTheme(stored);
})();

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
  applyFontStyle,

  /**
   * 닉네임에 '님' 자동 부착 (이미 '님'으로 끝나면 그대로)
   */
  withHonorific(name) {
    if (!name) return '어린양님';
    return name.endsWith('님') ? name : `${name}님`;
  },

  /**
   * 시간대별 인사말 가져오기
   * @param {string} name - 사용자 이름 (님 없이)
   * @returns {string} 인사말 (님 자동 부착)
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

    const displayName = name.endsWith('님') ? name : `${name}님`;
    return `${base}, ${displayName}`;
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
