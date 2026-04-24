/**
 * 주만나 AI 큐티 - localStorage 헬퍼
 * DATA_SCHEMA.md 기준
 */

const Storage = {
  /**
   * 기본 닉네임 (최초 방문 시 할당)
   */
  DEFAULT_NICKNAME: '어린양님',

  /**
   * 값 가져오기
   */
  get(key, defaultValue = null) {
    try {
      const raw = localStorage.getItem(key);
      if (raw === null) return defaultValue;
      try {
        return JSON.parse(raw);
      } catch {
        return raw;
      }
    } catch (e) {
      console.error('Storage.get error:', e);
      return defaultValue;
    }
  },

  /**
   * 값 저장
   */
  set(key, value) {
    try {
      const data = typeof value === 'string' ? value : JSON.stringify(value);
      localStorage.setItem(key, data);
      return true;
    } catch (e) {
      console.error('Storage.set error:', e);
      return false;
    }
  },

  /**
   * 값 삭제
   */
  remove(key) {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (e) {
      console.error('Storage.remove error:', e);
      return false;
    }
  },

  // ========================================================================
  // 사용자
  // ========================================================================

  /**
   * 사용자 이름 가져오기 (없으면 기본값 설정하고 반환)
   */
  getUserName() {
    let name = this.get('user.name');
    if (!name) {
      name = this.DEFAULT_NICKNAME;
      this.set('user.name', name);
      this.set('user.joinedAt', new Date().toISOString());
    }
    return name;
  },

  /**
   * 사용자 이름 변경
   */
  setUserName(name) {
    const trimmed = (name || '').trim();
    if (!trimmed) return false;
    this.set('user.name', trimmed);
    return true;
  },

  // ========================================================================
  // 사용자 해시 (서버 신원 — 닉네임#5자리 형식)
  // ========================================================================

  getUserHash() {
    return this.get('user.hash', null);
  },

  setUserHash(hash) {
    this.set('user.hash', hash);
  },

  // ========================================================================
  // 스트릭(연속일)
  // ========================================================================

  getStreak() {
    return {
      current: this.get('streak.current', 0),
      longest: this.get('streak.longest', 0),
      lastDate: this.get('streak.lastDate', null),
      totalCompleted: this.get('streak.totalCompleted', 0),
    };
  },

  /**
   * 오늘 완료 처리 → 스트릭 업데이트
   */
  markCompleted() {
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = this._getYesterday();
    const streak = this.getStreak();

    // 이미 오늘 완료
    if (streak.lastDate === today) {
      return streak;
    }

    // 어제도 완료했으면 +1, 아니면 리셋
    const newCurrent = streak.lastDate === yesterday ? streak.current + 1 : 1;
    const newLongest = Math.max(newCurrent, streak.longest);

    this.set('streak.current', newCurrent);
    this.set('streak.longest', newLongest);
    this.set('streak.lastDate', today);
    this.set('streak.totalCompleted', streak.totalCompleted + 1);

    return this.getStreak();
  },

  _getYesterday() {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  },

  // ========================================================================
  // 일별 기록
  // ========================================================================

  getDailyRecord(date) {
    return {
      completed:       this.get(`records.${date}.completed`, false),
      prayed:          this.get(`records.${date}.prayed`, false),
      underlines:      this.get(`records.${date}.underlines`, []),
      emotions:        this.get(`records.${date}.emotions`, []),
      memo:            this.get(`records.${date}.memo`, ''),
      reflection:      this.get(`records.${date}.reflection`, ''),
      questionAnswers: this.get(`records.${date}.questionAnswers`, []),
      progressStep:    this.get(`records.${date}.progressStep`, 0),
    };
  },

  setDailyRecord(date, partial) {
    Object.entries(partial).forEach(([k, v]) => {
      this.set(`records.${date}.${k}`, v);
    });
  },

  /**
   * 오늘 이미 완료했는지
   */
  isTodayCompleted() {
    const today = new Date().toISOString().slice(0, 10);
    return this.get(`records.${today}.completed`, false);
  },

  // ========================================================================
  // 설정
  // ========================================================================

  getSettings() {
    return {
      theme: this.get('settings.theme', 'light'),
      fontSize: this.get('settings.fontSize', 'md'),
      fontStyle: this.get('settings.fontStyle', 'pretendard'),
      background: this.get('settings.background', 'default'),
    };
  },

  setSetting(key, value) {
    this.set(`settings.${key}`, value);
  },
};

// 모듈 export (ES6 환경)
if (typeof window !== 'undefined') {
  window.Storage = Storage;
}
