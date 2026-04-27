// AI_PROMPT.md 기준 검증. scripts/generate_ai.py 의 validate() 1:1 포팅입니다.

const FORBIDDEN_WORDS = ['여러분', '~해야만', '반드시 해야'];

export function validateAi(aiData) {
  const warnings = [];

  const summary = aiData.core_summary || [];
  if (summary.length !== 5) {
    warnings.push(`core_summary가 정확히 5줄이 아님 (현재 ${summary.length}줄)`);
  }

  const chars = aiData.characters || [];
  if (!(chars.length >= 1 && chars.length <= 3)) {
    warnings.push(`characters가 1~3명 범위를 벗어남 (현재 ${chars.length}명)`);
  }

  const app = aiData.application || [];
  if (app.length !== 3) {
    warnings.push(`application이 정확히 3개가 아님 (현재 ${app.length}개)`);
  }

  const prayer = aiData.prayer || [];
  if (!(prayer.length >= 8 && prayer.length <= 14)) {
    warnings.push(`prayer가 8~14줄 범위를 벗어남 (현재 ${prayer.length}줄)`);
  }

  const allText = JSON.stringify(aiData);
  for (const word of FORBIDDEN_WORDS) {
    if (allText.includes(word)) {
      warnings.push(`금지어 포함: '${word}'`);
    }
  }

  return warnings;
}
