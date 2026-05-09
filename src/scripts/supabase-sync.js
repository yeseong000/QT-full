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
   * 5자리 이상 레거시 해시는 자동으로 4자리로 변환한다.
   */
  async ensureUserHash() {
    let hash = Storage.getUserHash();

    if (hash) {
      const legacy = String(hash).match(/^(.+)#(\d+)$/);
      if (legacy && legacy[2].length >= 5) {
        try {
          const migrated = await this.migrateLegacyHash(hash);
          if (migrated) {
            Storage.setUserHash(migrated, { force: true });
            return migrated;
          }
        } catch (e) {
          console.warn('[Migration] 자동 변환 실패 — 기존 해시 유지:', e);
        }
      }
      return hash;
    }

    const nickname = Storage.getUserName();
    let attempts = 0;
    while (attempts < 5) {
      const num = String(Math.floor(1000 + Math.random() * 9000));
      const candidate = `${nickname}#${num}`;
      try {
        const ok = await this.registerHash(candidate, nickname);
        if (ok) {
          Storage.setUserHash(candidate);
          return candidate;
        }
        // 중복이면 다음 번호 시도
      } catch (e) {
        // 네트워크 오류: 로컬에 먼저 저장해 유지 (다음 방문 시 재등록 시도)
        console.warn('해시 서버 등록 실패 (로컬 저장):', e);
        Storage.setUserHash(candidate);
        return candidate;
      }
      attempts++;
    }
    return null;
  },

  /**
   * 레거시 5자리 이상 해시를 4자리로 자동 변환.
   * 후보 순서: 앞 4자리 → 뒤 4자리 → 랜덤(최대 5회).
   * 서버에 후보가 비어 있으면 그 번호로 등록하고, 기존 qt_records를
   * 새 해시로 복제한다. 성공 시 새 해시 문자열, 실패 시 null.
   */
  async migrateLegacyHash(oldHash) {
    const m = String(oldHash).match(/^(.+)#(\d+)$/);
    if (!m) return null;
    const nickname = m[1];
    const oldNum = m[2];
    if (oldNum.length < 5) return null;

    const candidates = [oldNum.slice(0, 4), oldNum.slice(-4)];
    for (let i = 0; i < 5; i++) {
      candidates.push(String(Math.floor(1000 + Math.random() * 9000)));
    }

    for (const newNum of candidates) {
      const newHash = `${nickname}#${newNum}`;
      if (newHash === oldHash) continue;

      let usable = false;
      try {
        usable = await this.registerHash(newHash, nickname);
        if (!usable) {
          // 이미 등록된 행이 우리(같은 닉네임) 것이면 이어서 사용 — 부분 실패 후 재시도 케이스.
          const existing = await this.lookupHash(newHash);
          if (existing && existing.nickname === nickname) usable = true;
        }
      } catch (e) {
        console.warn('[Migration] 등록 시도 실패:', newHash, e);
        continue;
      }
      if (!usable) continue;

      let copied = 0;
      try {
        const records = await this.fetchAllRecords(oldHash);
        if (Array.isArray(records)) {
          for (const r of records) {
            if (!r || !r.date) continue;
            await _req('POST', 'qt_records', {
              body: {
                user_hash:        newHash,
                date:             r.date,
                emotions:         r.emotions          || [],
                reflection:       r.reflection        || null,
                question_answers: r.question_answers  || [],
                memo:             r.memo              || null,
                completed:        r.completed         || false,
                progress_step:    r.progress_step     || 5,
                updated_at:       new Date().toISOString(),
              },
              prefer: 'resolution=merge-duplicates,return=minimal',
            });
            copied++;
          }
        }
      } catch (e) {
        console.warn('[Migration] 기록 복제 실패 (계속 진행):', e);
      }

      console.log(`[Migration] ${oldHash} → ${newHash} (${copied}건 복제)`);
      return newHash;
    }

    console.warn('[Migration] 모든 후보 등록 실패 — 기존 해시 유지.');
    return null;
  },

  /**
   * 다른 기기에서 쓰던 해시로 로컬 전체 복원.
   * 반환: { ok: boolean, reason?, recordCount? }
   */
  async restoreFromHash(userHash) {
    const trimmed = String(userHash || '').trim();
    if (!trimmed) return { ok: false, reason: 'empty' };
    if (!/^.+#\d{4}$/.test(trimmed)) return { ok: false, reason: 'format' };

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
