/**
 * 주만나 AI 큐티 - 공통 유틸
 */

const Common = {
  /**
   * 시간대별 인사말 가져오기
   * @param {string} name - 사용자 이름
   * @returns {string} 인사말
   */
  getGreeting(name = '어린양님') {
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

    return `${base}, ${name}`;
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
    return new Date().toISOString().slice(0, 10);
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
};

if (typeof window !== 'undefined') {
  window.Common = Common;
}
