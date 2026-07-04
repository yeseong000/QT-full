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
   * 닉네임 끝 '님' 호칭 제거. '님'은 표시용 호칭이지 신원의 일부가 아님.
   */
  _stripHonorific(name) {
    if (!name) return name;
    let s = String(name).trim();
    while (s.endsWith('님')) s = s.slice(0, -1).trim();
    return s;
  },

  /**
   * 사용자 이름 가져오기 (없으면 기본값 설정하고 반환).
   * 과거에 '님'이 붙어 저장된 값이 있으면 자동으로 정리해 다시 저장.
   */
  getUserName() {
    let name = this.get('user.name');
    if (!name) {
      name = this.DEFAULT_NICKNAME;
      this.set('user.name', name);
      this.set('user.joinedAt', new Date().toISOString());
      return name;
    }
    const cleaned = this._stripHonorific(name);
    if (cleaned !== name) this.set('user.name', cleaned || this.DEFAULT_NICKNAME);
    return cleaned || this.DEFAULT_NICKNAME;
  },

  /**
   * 사용자 이름 변경. 입력에 '님'이 붙어 있어도 호칭은 떼고 저장.
   */
  setUserName(name) {
    const trimmed = this._stripHonorific((name || '').trim());
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

    // 해시에서 닉네임 추출 (예: "어린양#12345" → "어린양"). '님' 호칭은 떼고 저장.
    const m = String(hash).match(/^(.+)#\d+$/);
    if (m) this.set('user.name', this._stripHonorific(m[1]) || this.DEFAULT_NICKNAME);

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
      fontSize: this.get('settings.fontSize', 'md'),
      fontStyle: this.get('settings.fontStyle', 'pretendard'),
    };
  },

  setSetting(key, value) {
    this.set(`settings.${key}`, value);
  },

  // ========================================================================
  // [1회성] 기록을 '콘텐츠 날짜'로 정렬하는 마이그레이션
  //  과거엔 새벽(자정~업데이트 전)에 묵상하면, 화면엔 '전날 묵상'이 떠도 기록은 달력상
  //  '오늘'(자정 넘어간 날짜)에 저장돼 하루 어긋났다. 이 마이그레이션이 그런 기록을
  //  실제 묵상한 날짜로 옮긴다. 홈·캘린더 어느 쪽을 먼저 열어도 1회 실행된다.
  //   · 판별: 기록 날짜 D에 QT 콘텐츠 파일이 없다 = 그날 화면엔 '이전 날' 콘텐츠가 떴다는 뜻
  //           → D 직전에서 콘텐츠가 실제 있는 가장 가까운 날짜 X로 옮긴다.
  //   · 안전장치: (1) 옮기기 전 전체 백업, (2) 대상에 이미 기록 있으면 손대지 않음(덮어쓰기 금지).
  // ========================================================================
  async _contentExists(date, cache) {
    if (cache && date in cache) return cache[date];
    let ok = false;
    // 배포(Vercel)에선 데이터가 /data/qt/ 절대경로로 서빙됨 → 어느 페이지에서 호출해도 동일.
    try { ok = (await fetch(`/data/qt/${date}.json`, { method: 'HEAD' })).ok; }
    catch (e) { ok = false; }
    if (cache) cache[date] = ok;
    return ok;
  },

  _shiftISO(iso, days) {
    const [y, m, d] = iso.split('-').map(Number);
    const dt = new Date(Date.UTC(y, m - 1, d));
    dt.setUTCDate(dt.getUTCDate() + days);
    return dt.toISOString().slice(0, 10);
  },

  // 그 날짜에 '의미 있는 기록'이 하나라도 있는지 (덮어쓰기 방지용)
  _hasMeaningfulRecord(date) {
    const r = this.getDailyRecord(date);
    return !!(r.completed || (r.progressStep && r.progressStep > 0)
      || (r.reflection && r.reflection.trim()) || (r.memo && r.memo.trim())
      || (Array.isArray(r.emotions) && r.emotions.length)
      || (Array.isArray(r.questionAnswers) && r.questionAnswers.some(a => a && a.trim()))
      || (Array.isArray(r.underlines) && r.underlines.length));
  },

  // 반환: 옮긴 목록 [{from, to}, ...] (없으면 [] 또는 undefined). 호출부가 이걸로 다시 그릴지 판단.
  async migrateContentDates() {
    const FLAG = 'migration.contentDate.v1';
    try {
      if (localStorage.getItem(FLAG)) return;

      // 1) 기록 있는 날짜 수집 + 원본 전체 백업(되돌리기 가능하도록)
      const cache = {};
      const backup = {};
      const dateSet = new Set();
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (!k || !k.startsWith('records.')) continue;
        backup[k] = localStorage.getItem(k);
        const m = k.match(/^records\.(\d{4}-\d{2}-\d{2})\./);
        if (m) dateSet.add(m[1]);
      }
      if (dateSet.size === 0) { localStorage.setItem(FLAG, 'no-records'); return []; }
      localStorage.setItem('records._backup_contentDate_v1', JSON.stringify(backup));

      // 2) 옮길 대상 계산
      const dates = [...dateSet].sort();
      const moves = [];
      const willOccupy = new Set();
      for (const D of dates) {
        if (await this._contentExists(D, cache)) continue;      // 정상 저장 — 그대로 둠
        let X = null;
        for (let i = 1; i <= 4; i++) {
          const cand = this._shiftISO(D, -i);
          if (await this._contentExists(cand, cache)) { X = cand; break; }
        }
        if (!X) continue;                                       // 근처에 콘텐츠 없음 — 손대지 않음
        if (this._hasMeaningfulRecord(X) || willOccupy.has(X)) continue;  // 덮어쓰기 금지
        moves.push({ from: D, to: X });
        willOccupy.add(X);
      }

      // 3) 이동 실행 (localStorage 키 재배치)
      for (const { from, to } of moves) {
        const prefix = `records.${from}.`;
        Object.keys(backup).forEach(k => {
          if (!k.startsWith(prefix)) return;
          localStorage.setItem(`records.${to}.${k.slice(prefix.length)}`, backup[k]);
          localStorage.removeItem(k);
        });
      }
      localStorage.setItem(FLAG, `done:${moves.length}`);
      if (moves.length) console.log('[ContentDateMigration] 이동한 기록:', moves);

      // 4) 서버(Supabase) 정리 — 로드돼 있고 해시 있으면 best-effort (새 날짜에 기록 후 옛 행 제거)
      if (moves.length && typeof SupabaseSync !== 'undefined' && SupabaseSync.isConfigured()) {
        const hash = this.getUserHash();
        if (hash) {
          for (const { from, to } of moves) {
            try {
              await SupabaseSync.syncRecord(hash, to, this.getDailyRecord(to));
              await SupabaseSync.deleteRecord(hash, from);
            } catch (e) { console.warn('[ContentDateMigration] 서버 정리 실패:', from, '→', to, e); }
          }
        }
      }
      return moves;
    } catch (e) {
      // 실패해도 원본은 records._backup_contentDate_v1 에 안전하게 남는다.
      console.warn('[ContentDateMigration] 실패:', e);
    }
  },
};

// 모듈 export (ES6 환경)
if (typeof window !== 'undefined') {
  window.Storage = Storage;
}
