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
};

if (typeof window !== 'undefined') window.SupabaseSync = SupabaseSync;
