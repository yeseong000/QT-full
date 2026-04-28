// OpenAI 대신 Anthropic Claude API를 사용합니다.
// 한국 등 일부 지역에서 OpenAI API가 403을 반환하는 문제를 우회합니다.

import { SYSTEM_PROMPT, REFINE_SYSTEM_PROMPT, buildUserPrompt, buildRefinePrompt } from './prompts.js';
import { log } from './util.js';

const MODEL = 'claude-haiku-4-5-20251001';
const PRICE_INPUT_PER_1M = 0.80;
const PRICE_OUTPUT_PER_1M = 4.00;
const USD_TO_KRW = 1400;
const CLAUDE_URL = 'https://api.anthropic.com/v1/messages';
const MAX_TOKENS = 4096;

function calcCost(usage) {
  const costUsd =
    (usage.input_tokens / 1_000_000) * PRICE_INPUT_PER_1M +
    (usage.output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M;
  return {
    input_tokens: usage.input_tokens,
    output_tokens: usage.output_tokens,
    total_tokens: usage.input_tokens + usage.output_tokens,
    cost_usd: Math.round(costUsd * 1_000_000) / 1_000_000,
    cost_krw: Math.round(costUsd * USD_TO_KRW * 100) / 100,
  };
}

async function callClaude(apiKey, systemPrompt, userPrompt, temperature, prefill = '{') {
  const messages = [
    { role: 'user', content: userPrompt },
    { role: 'assistant', content: prefill },
  ];

  const res = await fetch(CLAUDE_URL, {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: MODEL,
      system: systemPrompt,
      messages,
      max_tokens: MAX_TOKENS,
      temperature,
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Claude API ${res.status}: ${errText.slice(0, 500)}`);
  }

  return await res.json();
}

async function callPass1(apiKey, qtData) {
  const userPrompt = buildUserPrompt(qtData);
  const response = await callClaude(apiKey, SYSTEM_PROMPT, userPrompt, 0.7);

  const rawText = response.content?.[0]?.text;
  if (!rawText) throw new Error('1차 응답 본문이 비어있습니다');

  const jsonText = '{' + rawText;
  const aiData = JSON.parse(jsonText);
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
  const prefill = '{\n  "application":';
  const response = await callClaude(apiKey, REFINE_SYSTEM_PROMPT, userPrompt, 0.3, prefill);

  const rawText = response.content?.[0]?.text;
  if (!rawText) throw new Error('2차 응답 본문이 비어있습니다');

  const jsonText = prefill + rawText;
  const result = JSON.parse(jsonText);
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
