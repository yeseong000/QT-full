// =============================================================
// Supabase 설정 — supabase.com에서 프로젝트 생성 후 아래 두 값을 채워주세요.
// anon key는 클라이언트 공개용 키입니다 (GitHub 업로드 허용).
// =============================================================
const SUPABASE_URL  = 'https://bftuoumpjeamdnfawagx.supabase.co';
const SUPABASE_ANON = 'sb_publishable_slRhiMby48sElbv-e_7uyA_SZvwZ237';

function _headers(extra) {
  return Object.assign({
    'apikey':        SUPABASE_ANON,
    'Authorization': `Bearer ${SUPABASE_ANON}`,
    'Content-Type':  'application/json',
  }, extra);
}

async function _req(method, table, { qs = '', body, prefer } = {}) {
  const url = `${SUPABASE_URL}/rest/v1/${table}${qs ? '?' + qs : ''}`;
  const res = await fetch(url, {
    method,
    headers: _headers(prefer ? { 'Prefer': prefer } : {}),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`[Supabase] ${method} ${table} → ${res.status} ${await res.text()}`);
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

const SupabaseSync = {
  // Supabase 자격증명이 채워졌는지 확인
  isConfigured() {
    return SUPABASE_URL !== 'https://YOUR_PROJECT.supabase.co' && SUPABASE_ANON !== 'YOUR_ANON_KEY';
  },

  // 해시 등록 — 중복이면 false, 성공이면 true
  // resolution=ignore-duplicates: 충돌 시 INSERT 건너뜀 → 반환 배열이 비어있으면 충돌
  async registerHash(userHash, nickname) {
    const rows = await _req('POST', 'qt_users', {
      body:   { user_hash: userHash, nickname },
      prefer: 'return=representation,resolution=ignore-duplicates',
    });
    return Array.isArray(rows) && rows.length > 0;
  },

  // 오늘 기록 서버 동기화 (묵상 완료 버튼 클릭 시에만 호출)
  async syncRecord(userHash, date, record) {
    await _req('POST', 'qt_records', {
      body: {
        user_hash:        userHash,
        date,
        emotions:         record.emotions        || [],
        reflection:       record.reflection       || null,
        question_answers: record.questionAnswers  || [],
        memo:             record.memo             || null,
        completed:        record.completed        || false,
        progress_step:    record.progressStep     || 5,
        updated_at:       new Date().toISOString(),
      },
      prefer: 'resolution=merge-duplicates,return=minimal',
    });
  },

  // 다른 기기에서 복원 — 해시로 전체 기록 가져오기
  async fetchAllRecords(userHash) {
    return await _req('GET', 'qt_records', {
      qs: `user_hash=eq.${encodeURIComponent(userHash)}&order=date.desc`,
    });
  },

  // 해시 존재 여부 조회 (복원용)
  async lookupHash(userHash) {
    const rows = await _req('GET', 'qt_users', {
      qs: `user_hash=eq.${encodeURIComponent(userHash)}`,
    });
    return Array.isArray(rows) && rows.length > 0 ? rows[0] : null;
  },

  /**
   * 로컬에 해시가 있으면 그대로, 없으면 새로 만들어 서버에 등록.
   * 첫 방문/첫 묵상 모두 같은 진입점으로 사용.
   */
  async ensureUserHash() {
    let hash = Storage.getUserHash();
    if (hash) return hash;

    const nickname = Storage.getUserName();
    let attempts = 0;
    while (attempts < 5) {
      const num = String(Math.floor(10000 + Math.random() * 90000));
      const candidate = `${nickname}#${num}`;
      try {
        const ok = await this.registerHash(candidate, nickname);
        if (ok) {
          Storage.setUserHash(candidate);
          return candidate;
        }
      } catch (e) {
        console.warn('해시 등록 실패:', e);
        return null;
      }
      attempts++;
    }
    return null;
  },

  /**
   * 다른 기기에서 쓰던 해시로 로컬 전체 복원.
   * 반환: { ok: boolean, reason?, recordCount? }
   */
  async restoreFromHash(userHash) {
    const trimmed = String(userHash || '').trim();
    if (!trimmed) return { ok: false, reason: 'empty' };
    if (!/^.+#\d{5}$/.test(trimmed)) return { ok: false, reason: 'format' };

    try {
      const user = await this.lookupHash(trimmed);
      if (!user) return { ok: false, reason: 'not_found' };

      const records = await this.fetchAllRecords(trimmed);
      Storage.restoreFromServer(trimmed, records || []);
      return { ok: true, recordCount: (records || []).length };
    } catch (e) {
      console.warn('복원 실패:', e);
      return { ok: false, reason: 'network' };
    }
  },
};

if (typeof window !== 'undefined') window.SupabaseSync = SupabaseSync;
