// Discord Webhook 으로 실패 알림을 발송합니다.
// 무료, 도메인 검증 불필요, 셋업 5분.

import { log } from './util.js';

async function postDiscord(env, content) {
  if (!env.DISCORD_WEBHOOK_URL) {
    log('WARN', '알림 환경변수가 없어 디스코드 발송 생략');
    return;
  }

  try {
    const res = await fetch(env.DISCORD_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });

    if (!res.ok) {
      const t = await res.text();
      log('WARN', `디스코드 발송 실패 ${res.status}: ${t.slice(0, 200)}`);
      return;
    }
    log('OK', '알림 디스코드 발송 완료');
  } catch (e) {
    log('WARN', `디스코드 발송 예외: ${e.message}`);
  }
}

export async function notifyFailure(env, date, error) {
  const msg = [
    `❌ **주만나 QT 자동 생성 실패** (${date})`,
    '```',
    `에러: ${error?.message || String(error)}`,
    '```',
    'Cloudflare Dashboard → Workers → jumanna-qt-daily → Logs 에서 자세한 로그를 확인하세요.',
    '백업 워크플로가 KST 05:00 에 다시 시도합니다.',
  ].join('\n');
  await postDiscord(env, msg);
}

export async function notifySuccess(env, date, title, scriptureRef) {
  const msg = `✅ **${date}** · ${title} (${scriptureRef}) 묵상 생성 완료`;
  await postDiscord(env, msg);
}
