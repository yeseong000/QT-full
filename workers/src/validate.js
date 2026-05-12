// AI_PROMPT.md 기준 검증. scripts/generate_ai.py 의 validate() 1:1 포팅입니다.

const FORBIDDEN_WORDS = ['여러분', '~해야만', '반드시 해야'];

export function validateAi(aiData) {
  const warnings = [];

  // scenes: 5개
  const scenes = aiData.scenes || [];
  if (scenes.length !== 5) {
    warnings.push(`scenes가 정확히 5개가 아님 (현재 ${scenes.length}개)`);
  }

  // book_overview 검증: 객체(4필드)이며 옛 문자열도 폴백으로 허용
  const bo = aiData.book_overview;
  if (!bo) {
    warnings.push('book_overview 필드 없음');
  } else if (typeof bo === 'object' && !Array.isArray(bo)) {
    for (const key of ['author', 'date', 'place', 'core']) {
      if (!bo[key]) warnings.push(`book_overview.${key} 비어 있음`);
    }
  } else if (typeof bo === 'string') {
    if (bo.length < 30) warnings.push(`book_overview 문자열이 너무 짧음 (${bo.length}자)`);
  }

  // passage_intro 존재 확인
  if (!aiData.passage_intro) {
    warnings.push('passage_intro 필드 없음');
  }

  // characters: 1~3명
  const chars = aiData.characters || [];
  if (!(chars.length >= 1 && chars.length <= 3)) {
    warnings.push(`characters가 1~3명 범위를 벗어남 (현재 ${chars.length}명)`);
  }

  // application: 정확히 3개
  const app = aiData.application || [];
  if (app.length !== 3) {
    warnings.push(`application이 정확히 3개가 아님 (현재 ${app.length}개)`);
  }

  // prayer: 10~13줄 (빈 줄 포함)
  const prayer = aiData.prayer || [];
  if (!(prayer.length >= 10 && prayer.length <= 13)) {
    warnings.push(`prayer가 10~13줄 범위를 벗어남 (현재 ${prayer.length}줄)`);
  }

  // 금지어 검사
  const allText = JSON.stringify(aiData);
  for (const word of FORBIDDEN_WORDS) {
    if (allText.includes(word)) {
      warnings.push(`금지어 포함: '${word}'`);
    }
  }

  return warnings;
}
