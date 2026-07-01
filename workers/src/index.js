// Cloudflare Worker — 타이머(알람시계) 역할만 담당합니다.
// 매일 KST 04:00 에 본진 워크플로우(daily_qt.yml)의 workflow_dispatch를 정확히 호출합니다.
// (GitHub 자체 cron은 잘 늦으므로, 워커가 정시에 깨우는 유일한 트리거 창구입니다.)
// 크롤링·AI 생성·커밋은 GitHub Actions(미국 서버)에 위임합니다.
// daily_qt_backup.yml 은 워커가 실패했을 때만 KST 06:00 자체 cron으로 도는 안전망입니다.

import { notifyFailure } from './notify.js';
import { log, todayKst } from './util.js';

const WORKFLOW_FILE = 'daily_qt.yml';

async function triggerGitHubActions(env) {
  const [owner, repo] = env.GITHUB_REPO.split('/');
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
      'User-Agent': 'jumanna-qt-daily-worker',
    },
    body: JSON.stringify({ ref: 'main' }),
  });

  // GitHub Actions dispatch 성공 시 204 No Content 반환
  if (res.status !== 204) {
    const errText = await res.text();
    throw new Error(`GitHub Actions 트리거 실패 ${res.status}: ${errText.slice(0, 300)}`);
  }

  log('OK', `GitHub Actions 트리거 완료 (${WORKFLOW_FILE})`);
}

async function run(env) {
  const date = todayKst();
  log('INFO', `===== Cloudflare Worker 시작 (${date}) =====`);

  try {
    await triggerGitHubActions(env);
    log('INFO', '===== 트리거 완료 — GitHub Actions가 이어서 처리합니다 =====');
  } catch (err) {
    log('ERR', `트리거 실패: ${err.message}`);
    await notifyFailure(env, date, err);
    throw err;
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env));
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/run') {
      try {
        await run(env);
        return new Response('OK — GitHub Actions 트리거 완료', {
          status: 200,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
      } catch (err) {
        return new Response(`FAIL: ${err.message}`, {
          status: 500,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
      }
    }
    return new Response('주만나 QT Daily Worker. GET /run 으로 수동 실행하세요.', {
      status: 200,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  },
};
