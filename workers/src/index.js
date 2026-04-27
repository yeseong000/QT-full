// 주만나 QT 일일 자동화 Worker 진입점.
// scheduled() 핸들러는 매일 KST 05:00 에 Cron Trigger로 호출됩니다.
// fetch() 핸들러는 GET /run 으로 수동 트리거할 때 사용합니다.

import { fetchQt } from './fetch_qt.js';
import { generateAi } from './generate_ai.js';
import { commitJson } from './github.js';
import { notifyFailure } from './notify.js';
import { validateAi } from './validate.js';
import { log, nowKstIso, todayKst } from './util.js';

async function runPipeline(env) {
  const date = todayKst();
  log('INFO', `===== 파이프라인 시작 (${date}) =====`);

  let qtData;
  try {
    qtData = await fetchQt();
  } catch (err) {
    log('ERR', `QT 크롤링 실패: ${err.message}`);
    await notifyFailure(env, date, err);
    throw err;
  }

  let aiResult;
  try {
    aiResult = await generateAi(qtData, env.OPENAI_API_KEY);
  } catch (err) {
    log('ERR', `AI 생성 실패: ${err.message}`);
    await notifyFailure(env, date, err);
    throw err;
  }

  const { aiData, costInfo, model } = aiResult;

  const warnings = validateAi(aiData);
  for (const w of warnings) log('WARN', w);
  if (warnings.length === 0) log('OK', '검증 통과 ✓');

  const aiResultPayload = {
    date,
    scripture_ref: qtData.scripture_ref,
    title: qtData.title,
    ...aiData,
    generated_at: nowKstIso(),
    model,
    _cost: costInfo,
  };

  try {
    await commitJson(env, `data/qt/${date}.json`, qtData,
      `chore(data): 자동 크롤링 · ${date} QT (Worker)`);
    await commitJson(env, `data/ai/${date}.json`, aiResultPayload,
      `chore(data): 자동 크롤링 · ${date} AI 묵상 (Worker)`);
  } catch (err) {
    log('ERR', `GitHub 커밋 실패: ${err.message}`);
    await notifyFailure(env, date, err);
    throw err;
  }

  log('INFO', `===== 파이프라인 완료 (${date}) =====`);
}

export default {
  // Cron Trigger 진입점
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runPipeline(env));
  },

  // 수동 트리거: GET /run
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/run') {
      try {
        await runPipeline(env);
        return new Response('OK', {
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
