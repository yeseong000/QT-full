// 한국 표준시 (KST = UTC+9) 기준 오늘 날짜를 'YYYY-MM-DD' 형태로 반환
export function todayKst() {
  const now = new Date();
  const kstMs = now.getTime() + 9 * 60 * 60 * 1000;
  return new Date(kstMs).toISOString().slice(0, 10);
}

// KST 기준 ISO 8601 (예: "2026-04-25T05:00:12.345+09:00")
export function nowKstIso() {
  const now = new Date();
  const kstMs = now.getTime() + 9 * 60 * 60 * 1000;
  const iso = new Date(kstMs).toISOString().replace('Z', '+09:00');
  return iso;
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// 'Set-Cookie' 헤더에서 name=value 만 뽑아 합칩니다.
// Cloudflare Workers fetch 응답은 여러 Set-Cookie 헤더를 단일 문자열로 합쳐서 줍니다.
// 우리는 만료/도메인 같은 메타는 무시하고 name=value 들만 다음 요청에 같이 보냅니다.
export function extractCookies(response) {
  const setCookieHeader = response.headers.get('set-cookie');
  if (!setCookieHeader) return '';

  const cookies = [];
  // 단일 문자열 안에 여러 Set-Cookie가 콤마로 연결되어 있을 수 있으므로
  // ", " 로 분리하지 말고 ';' 로 첫 토큰만 취하는 방식으로 안전하게 파싱합니다.
  // Workers의 getSetCookie()가 가능하면 우선 사용.
  if (typeof response.headers.getSetCookie === 'function') {
    for (const raw of response.headers.getSetCookie()) {
      const firstPair = raw.split(';')[0].trim();
      if (firstPair) cookies.push(firstPair);
    }
  } else {
    // Fallback: 단일 헤더 문자열에서 첫 ';' 까지가 첫 쿠키
    const firstPair = setCookieHeader.split(';')[0].trim();
    if (firstPair) cookies.push(firstPair);
  }

  return cookies.join('; ');
}

// 한글이 섞인 문자열을 안전하게 base64로 변환 (GitHub Contents API용)
export function utf8ToBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

// 단순 로깅 (Cloudflare Workers 로그에 그대로 찍힘)
export function log(level, msg) {
  const time = nowKstIso().slice(11, 19);
  const prefix = { INFO: 'ℹ️', OK: '✅', WARN: '⚠️', ERR: '❌' }[level] || '•';
  console.log(`[${time}] ${prefix} ${msg}`);
}
