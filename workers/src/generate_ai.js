// scripts/generate_ai.py 의 generate_real() 2-pass 흐름을 그대로 옮긴 파일입니다.

import { SYSTEM_PROMPT, REFINE_SYSTEM_PROMPT, buildUserPrompt, buildRefinePrompt } from './prompts.js';
import { log } from './util.js';

const MODEL = 'gpt-4o-mini';
const PRICE_INPUT_PER_1M = 0.15;
const PRICE_OUTPUT_PER_1M = 0.60;
const USD_TO_KRW = 1500;
const OPENAI_URL = 'https://api.openai.com/v1/chat/completions';

function calcCost(usage) {
  const costUsd =
    (usage.prompt_tokens / 1_000_000) * PRICE_INPUT_PER_1M +
    (usage.completion_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M;
  return {
    input_tokens: usage.prompt_tokens,
    output_tokens: usage.completion_tokens,
    total_tokens: usage.total_tokens,
    cost_usd: Math.round(costUsd * 1_000_000) / 1_000_000,
    cost_krw: Math.round(costUsd * USD_TO_KRW * 100) / 100,
  };
}

async function callOpenAI(apiKey, messages, temperature) {
  const res = await fetch(OPENAI_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: MODEL,
      messages,
      response_format: { type: 'json_object' },
      temperature,
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`OpenAI API ${res.status}: ${errText.slice(0, 500)}`);
  }

  return await res.json();
}

async function callPass1(apiKey, qtData) {
  const userPrompt = buildUserPrompt(qtData);
  const response = await callOpenAI(
    apiKey,
    [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: userPrompt },
    ],
    0.7,
  );

  const content = response.choices?.[0]?.message?.content;
  if (!content) throw new Error('1차 응답 본문이 비어있습니다');

  const aiData = JSON.parse(content);
  const cost = calcCost(response.usage);
  log(
    'OK',
    `1차 토큰: ${cost.total_tokens} ` +
      `(입력 ${cost.input_tokens} / 출력 ${cost.output_tokens}) ` +
      `/ 비용: ${cost.cost_krw.toFixed(2)}원`,
  );
  return [aiData, cost];
}

async function callPass2(apiKey, application, qtData) {
  const userPrompt = buildRefinePrompt(application, qtData);
  const response = await callOpenAI(
    apiKey,
    [
      { role: 'system', content: REFINE_SYSTEM_PROMPT },
      { role: 'user', content: userPrompt },
    ],
    0.3,
  );

  const content = response.choices?.[0]?.message?.content;
  if (!content) throw new Error('2차 응답 본문이 비어있습니다');

  const result = JSON.parse(content);
  const refined = result.application;
  if (!Array.isArray(refined) || refined.length !== 3) {
    throw new Error('2차 정제 결과 구조 오류: application이 3개 리스트가 아님');
  }
  const cost = calcCost(response.usage);
  log(
    'OK',
    `2차 토큰: ${cost.total_tokens} ` +
      `(입력 ${cost.input_tokens} / 출력 ${cost.output_tokens}) ` +
      `/ 비용: ${cost.cost_krw.toFixed(2)}원`,
  );
  return [refined, cost];
}

const ZERO_COST = {
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  cost_usd: 0,
  cost_krw: 0,
};

export async function generateAi(qtData, apiKey) {
  log('INFO', `1차 생성 중 (모델: ${MODEL}, temperature=0.7)...`);
  const [aiData, cost1] = await callPass1(apiKey, qtData);

  log('INFO', '2차 application 정제 중 (temperature=0.3)...');
  let cost2 = ZERO_COST;
  try {
    const [refinedApp, c2] = await callPass2(apiKey, aiData.application, qtData);
    aiData.application = refinedApp;
    cost2 = c2;
  } catch (e) {
    log('WARN', `2차 정제 실패, 1차 결과 그대로 사용: ${e.message}`);
  }

  const costInfo = {
    input_tokens: cost1.input_tokens + cost2.input_tokens,
    output_tokens: cost1.output_tokens + cost2.output_tokens,
    total_tokens: cost1.total_tokens + cost2.total_tokens,
    cost_usd: Math.round((cost1.cost_usd + cost2.cost_usd) * 1_000_000) / 1_000_000,
    cost_krw: Math.round((cost1.cost_krw + cost2.cost_krw) * 100) / 100,
    breakdown: { pass1: cost1, pass2: cost2 },
  };

  log(
    'OK',
    `합계 토큰: ${costInfo.total_tokens} ` +
      `/ 비용: $${costInfo.cost_usd.toFixed(6)} (약 ${costInfo.cost_krw.toFixed(2)}원)`,
  );

  return { aiData, costInfo, model: MODEL };
}
