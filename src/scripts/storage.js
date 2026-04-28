/**
 * 주만나 AI 큐티 - localStorage 헬퍼
 * DATA_SCHEMA.md 기준
 */

const Storage = {
  /**
   * 기본 닉네임 (최초 방문 시 할당)
   */
  DEFAULT_NICKNAME: '어린양',

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
  // 사용자 해시 (서버 신원 — 닉네임#4자리 형식)
  // ========================================================================

  getUserHash() {
    return this.get('user.hash', null);
  },

  /**
   * 해시 저장 — 한 번 박제되면 절대 덮어쓰지 않음.
   * 다른 기기에서 불러오기로 복원할 때만 force=true 사용.
   */
  setUserHash(hash, { force = false } = {}) {
    if (!hash) return false;
    if (!force && this.get('user.hash', null)) return false;
    this.set('user.hash', hash);
    return true;
  },

  /**
   * 서버에서 받은 해시 + 기록 묶음으로 localStorage 전체 복원.
   * 캐시가 지워졌거나 다른 기기에서 처음 로그인할 때 사용.
   */
  restoreFromServer(hash, records) {
    this.set('user.hash', hash);

    // 해시에서 닉네임 추출 (예: "어린양#12345" → "어린양")
    const m = String(hash).match(/^(.+)#\d+$/);
    if (m) this.set('user.name', m[1]);

    if (Array.isArray(records)) {
      records.forEach((r) => {
        if (!r || !r.date) return;
        this.setDailyRecord(r.date, {
          completed:       !!r.completed,
          emotions:        r.emotions          || [],
          reflection:      r.reflection        || '',
          questionAnswers: r.question_answers  || [],
          memo:            r.memo              || '',
          progressStep:    r.progress_step     || (r.completed ? 5 : 0),
        });
      });
      this._recalculateStreak(records);
    }
  },

  /**
   * 서버 기록 배열에서 스트릭 정보를 다시 계산해 localStorage에 반영.
   * (스트릭 자체는 서버에 저장하지 않으므로 날짜 리스트로부터 유도.)
   */
  _recalculateStreak(records) {
    const dates = records
      .filter((r) => r && r.completed && r.date)
      .map((r) => r.date)
      .sort();

    if (dates.length === 0) return;

    const totalCompleted = dates.length;
    const lastDate = dates[dates.length - 1];

    // 최장 연속 (longest)
    let longest = 1;
    let run = 1;
    for (let i = 1; i < dates.length; i++) {
      const diff = (new Date(dates[i]) - new Date(dates[i - 1])) / 86400000;
      if (diff === 1) {
        run++;
        if (run > longest) longest = run;
      } else {
        run = 1;
      }
    }

    // 현재 연속 (current) — 마지막 완료일이 오늘/어제일 때만 유효
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = this._getYesterday();
    let current = 0;
    if (lastDate === today || lastDate === yesterday) {
      current = 1;
      for (let i = dates.length - 2; i >= 0; i--) {
        const diff = (new Date(dates[i + 1]) - new Date(dates[i])) / 86400000;
        if (diff === 1) current++;
        else break;
      }
    }

    this.set('streak.current', current);
    this.set('streak.longest', longest);
    this.set('streak.lastDate', lastDate);
    this.set('streak.totalCompleted', totalCompleted);
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

  // ========================================================================
  // 밑줄 (하이라이트) 헬퍼
  // ========================================================================

  /**
   * 해당 날짜의 밑줄 배열 반환
   */
  getUnderlines(date) {
    return this.get(`records.${date}.underlines`, []);
  },

  /**
   * 새 밑줄 추가 (객체 그대로 push)
   */
  addUnderline(date, underline) {
    const list = this.getUnderlines(date);
    list.push(underline);
    this.set(`records.${date}.underlines`, list);
    return underline;
  },

  /**
   * id로 밑줄 부분 업데이트 (메모 추가/수정 등)
   */
  updateUnderline(date, id, partial) {
    const list = this.getUnderlines(date);
    const idx = list.findIndex(u => u.id === id);
    if (idx === -1) return null;
    list[idx] = { ...list[idx], ...partial };
    this.set(`records.${date}.underlines`, list);
    return list[idx];
  },

  /**
   * id로 밑줄 제거
   */
  removeUnderline(date, id) {
    const list = this.getUnderlines(date);
    const next = list.filter(u => u.id !== id);
    this.set(`records.${date}.underlines`, next);
    return list.length !== next.length;
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
      fontStyle: this.get('settings.fontStyle', 'noto-serif'),
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
