/**
 * 주만나 AI 큐티 — Service Worker
 *
 * 목적: iOS PWA의 공격적 launch URL snapshot 캐시를 우회.
 *   - iOS Safari PWA는 홈 아이콘 launch 시 옛 HTML/CSS/JS를 자체 caching → 새 deploy 안 보임 (WebKit Bug #199110)
 *   - SW가 모든 fetch를 가로채서 network-first로 처리 → 항상 최신 콘텐츠 우선
 *   - 오프라인 시에만 캐시 사용 (offline fallback)
 *
 * 한 번 설치되면 다음 페이지 navigation부터 자동 적용. 새 SW 버전 push 시:
 *   1. install: skipWaiting()으로 즉시 대기열에서 활성화
 *   2. activate: 옛 캐시 삭제 + clients.claim()으로 즉시 제어권 인수
 *   3. 다음 fetch부터 새 SW가 처리
 *
 * 배포 시 새 코드를 반영하려면 SW_VERSION을 bump해야 옛 캐시가 비워짐.
 * (SW 코드 자체가 안 바뀌면 iOS도 SW 재설치 안 함 → 그래서 버전 bump 필수)
 */

const SW_VERSION = 'v20260722-001';
const CACHE_NAME = `hainaqt-${SW_VERSION}`;
const OFFLINE_FALLBACK = '/src/index.html';

// ───────────────────────────────────────────────────────────────────────────
// 라이프사이클
// ───────────────────────────────────────────────────────────────────────────

self.addEventListener('install', (event) => {
  // 기존 SW가 활성 상태여도 새 버전을 곧장 activate 단계로 진행
  // (네트워크 우선 전략이라 안전: 기존 페이지가 망가지지 않음)
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // 1) 이 SW 버전의 캐시 외엔 모두 삭제
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter(name => name.startsWith('hainaqt-') && name !== CACHE_NAME)
        .map(name => caches.delete(name))
    );
    // 2) 모든 열려있는 클라이언트(탭/PWA 윈도우)의 제어권 즉시 인수
    await self.clients.claim();
  })());
});

// ───────────────────────────────────────────────────────────────────────────
// fetch 인터셉트 — network-first 전략
// ───────────────────────────────────────────────────────────────────────────

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // GET 외엔 인터셉트 안 함 (POST/PUT 등 그대로 통과)
  if (req.method !== 'GET') return;

  // 동일 출처(same-origin)만 처리. 외부 CDN(Pretendard, Google Fonts 등)은 브라우저 기본 캐시.
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // http(s)만 (chrome-extension://, data: 등 무시)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;

  event.respondWith((async () => {
    try {
      // ① 네트워크 우선
      const networkResponse = await fetch(req);

      // 성공 응답만 캐시에 저장 (offline 대비용 — 정상 사용 시엔 cache 안 봄)
      if (networkResponse.ok) {
        const cache = await caches.open(CACHE_NAME);
        // response는 한 번만 읽을 수 있으니 clone
        cache.put(req, networkResponse.clone()).catch(() => { /* quota 등 무시 */ });
      }

      return networkResponse;
    } catch (err) {
      // ② 네트워크 실패 → 캐시 fallback
      const cached = await caches.match(req);
      if (cached) return cached;

      // ③ 캐시에도 없음 + navigate 요청 → index.html로 fallback
      if (req.mode === 'navigate') {
        const fallback = await caches.match(OFFLINE_FALLBACK);
        if (fallback) return fallback;
      }

      // 그 외엔 그대로 에러 던짐
      throw err;
    }
  })());
});

// ───────────────────────────────────────────────────────────────────────────
// 클라이언트 메시지 처리 (필요 시 페이지에서 'SKIP_WAITING' 보내면 즉시 활성화)
// ───────────────────────────────────────────────────────────────────────────

self.addEventListener('message', (event) => {
  if (!event.data) return;
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (event.data.type === 'GET_VERSION') {
    // 디버그 칩에서 SW 버전 조회 — MessageChannel port로 응답
    if (event.ports && event.ports[0]) {
      event.ports[0].postMessage({ version: SW_VERSION, cacheName: CACHE_NAME });
    }
  }
});
