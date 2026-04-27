// GitHub Contents API 래퍼.
// 같은 경로에 파일이 이미 있으면 sha를 함께 보내 갱신, 없으면 신규 생성합니다.

import { log, utf8ToBase64 } from './util.js';

const API_BASE = 'https://api.github.com';

function authHeaders(token) {
  return {
    'Authorization': `Bearer ${token}`,
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'jumanna-qt-daily-worker',
  };
}

async function getExistingSha(env, path) {
  const url = `${API_BASE}/repos/${env.GITHUB_REPO}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}?ref=${encodeURIComponent(env.GITHUB_BRANCH)}`;
  const res = await fetch(url, { headers: authHeaders(env.GITHUB_TOKEN) });
  if (res.status === 404) return null;
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`GitHub GET ${path} 실패 ${res.status}: ${t.slice(0, 300)}`);
  }
  const body = await res.json();
  return body.sha || null;
}

export async function commitJson(env, path, data, commitMessage) {
  const jsonStr = JSON.stringify(data, null, 2);
  const contentB64 = utf8ToBase64(jsonStr);

  const sha = await getExistingSha(env, path);

  const url = `${API_BASE}/repos/${env.GITHUB_REPO}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}`;
  const body = {
    message: commitMessage,
    content: contentB64,
    branch: env.GITHUB_BRANCH,
    committer: {
      name: 'QT Bot (yeseong000)',
      email: '271984505+yeseong000@users.noreply.github.com',
    },
  };
  if (sha) body.sha = sha;

  const res = await fetch(url, {
    method: 'PUT',
    headers: { ...authHeaders(env.GITHUB_TOKEN), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const t = await res.text();
    throw new Error(`GitHub PUT ${path} 실패 ${res.status}: ${t.slice(0, 500)}`);
  }

  log('OK', `GitHub 커밋 완료: ${path}${sha ? ' (갱신)' : ' (신규)'}`);
}
