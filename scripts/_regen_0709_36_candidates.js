const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const DATE = "2026-07-09";
const MODEL = "gpt-4o";
const REQUIRED_CATEGORIES = [
  "주석형/본문관찰",
  "지명 정보",
  "어원·유래",
  "인물 배경",
  "문화·관습",
  "신학/해석 견해",
  "본문 디테일",
  "연결 질문",
  "랜덤",
];

function loadEnvFile(file) {
  if (!fs.existsSync(file)) return;
  const text = fs.readFileSync(file, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!m || process.env[m[1]]) continue;
    process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

loadEnvFile(path.join(ROOT, ".env"));
loadEnvFile("C:/Users/USER/Desktop/앱 개발/7.주만나 큐티/.env");

const API_KEY = process.env.OPENAI_API_KEY;
if (!API_KEY) {
  throw new Error("OPENAI_API_KEY is missing");
}

function readJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), "utf8"));
}

function writeJson(rel, data) {
  fs.writeFileSync(path.join(ROOT, rel), JSON.stringify(data, null, 2), "utf8");
}

function bodyText(qt) {
  return (qt.verses || []).map((v) => `${v.number} ${v.text}`).join("\n");
}

function sliceKb(kb, qt) {
  if (!kb || typeof kb !== "object") return null;
  const chapKeys = Object.keys(kb).filter((k) => /^\d+$/.test(k));
  if (!chapKeys.length) return kb;
  const start = qt.verses_start_chapter || qt.chapter;
  const end = qt.verses_end_chapter || qt.chapter || start;
  const wanted = new Set();
  for (let c = Number(start); c <= Number(end); c += 1) wanted.add(String(c));
  if (!chapKeys.some((k) => wanted.has(k))) return null;
  const out = {};
  for (const [k, v] of Object.entries(kb)) {
    if (k === "_단락구조") continue;
    if (!/^\d+$/.test(k) || wanted.has(k)) out[k] = v;
  }
  return out;
}

function bookFromRef(ref) {
  const m = String(ref || "").match(/^\s*([가-힣]+(?:상|하)?)\s+\d+:/);
  return m ? m[1] : "";
}

function flattenFollowups(items) {
  const out = [];
  for (const main of items || []) {
    if (main?.question) out.push(main.question);
    for (const tail of main?.follow_ups || []) {
      if (tail?.question) out.push(tail.question);
    }
  }
  return out;
}

function loadHistory(qt) {
  const dir = path.join(ROOT, "data", "deep_dive");
  const currentBook = qt.book_name || bookFromRef(qt.scripture_ref);
  const rows = [];
  for (const name of fs.readdirSync(dir).sort().reverse()) {
    if (!/^\d{4}-\d{2}-\d{2}\.json$/.test(name)) continue;
    const date = name.slice(0, 10);
    if (date >= DATE) continue;
    const deep = readJson(`data/deep_dive/${name}`);
    const book = bookFromRef(deep.scripture_ref || "") || currentBook;
    if (book !== currentBook) continue;
    for (const question of flattenFollowups(deep.follow_up_questions)) {
      rows.push({ date, question });
    }
  }
  return rows;
}

function norm(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

function overlap(a, b) {
  const na = norm(a);
  const nb = norm(b);
  if (!na || !nb) return false;
  if (na === nb) return true;
  // Containment only counts as overlap when both sides are long enough to be a
  // specific phrase, not a bare 2-3 syllable proper noun (e.g. "다윗") that
  // will trivially appear inside almost every question about this book.
  if (na.length < 4 || nb.length < 4) return false;
  return na.includes(nb) || nb.includes(na);
}

function longestCommonSubstring(a, b) {
  const aa = norm(a);
  const bb = norm(b);
  if (!aa || !bb) return 0;
  let prev = new Array(bb.length + 1).fill(0);
  let best = 0;
  for (let i = 1; i <= aa.length; i += 1) {
    const curr = new Array(bb.length + 1).fill(0);
    for (let j = 1; j <= bb.length; j += 1) {
      if (aa[i - 1] === bb[j - 1]) {
        curr[j] = prev[j - 1] + 1;
        if (curr[j] > best) best = curr[j];
      }
    }
    prev = curr;
  }
  // Normalize by the longer string, not the shorter one: a short generic
  // topic label (e.g. a person's name) fully contained in a long sentence
  // must not register as near-total overlap just because it's short.
  return best / Math.max(aa.length, bb.length);
}

function sameContext(a, b) {
  if (overlap(a, b)) return true;
  return longestCommonSubstring(a, b) >= 0.48;
}

function isDuplicate(candidate, selected, history) {
  if (/[왜]|이유/.test(candidate.question || "")) return true;
  if (/브에롯.*깃다임|깃다임.*브에롯/.test(candidate.question || "")) return true;
  if (/브에롯.*깃다임|깃다임.*브에롯/.test(candidate.topic || "")) return true;
  const topic = candidate.topic || candidate.question;
  for (const row of selected) {
    if (sameContext(topic, row.topic || row.question) || sameContext(candidate.question, row.question)) return true;
  }
  for (const row of history) {
    if (sameContext(topic, row.topic || row.question) || sameContext(candidate.question, row.question)) return true;
  }
  return false;
}

async function chat({ system, payload, schema, schemaName, temperature = 0.5, maxTokens = 4000 }) {
  const resp = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: MODEL,
      messages: [
        { role: "system", content: system },
        { role: "user", content: JSON.stringify(payload) },
      ],
      temperature,
      max_tokens: maxTokens,
      response_format: {
        type: "json_schema",
        json_schema: { name: schemaName, strict: true, schema },
      },
    }),
  });
  if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
  const json = await resp.json();
  return JSON.parse(json.choices[0].message.content);
}

const candidateSchema = {
  type: "object",
  properties: {
    candidates: {
      type: "array",
      minItems: 36,
      maxItems: 36,
      items: {
        type: "object",
        properties: {
          question: { type: "string" },
          category: { type: "string", enum: REQUIRED_CATEGORIES },
          topic: { type: "string" },
          source: { type: "string" },
          group_hint: { type: "string" },
        },
        required: ["question", "category", "topic", "source", "group_hint"],
        additionalProperties: false,
      },
    },
  },
  required: ["candidates"],
  additionalProperties: false,
};

const finalSchema = {
  type: "object",
  properties: {
    follow_up_questions: {
      type: "array",
      minItems: 3,
      maxItems: 3,
      items: {
        type: "object",
        properties: {
          question: { type: "string" },
          answer: { type: "string" },
          follow_ups: {
            type: "array",
            minItems: 2,
            maxItems: 2,
            items: {
              type: "object",
              properties: {
                question: { type: "string" },
                answer: { type: "string" },
              },
              required: ["question", "answer"],
              additionalProperties: false,
            },
          },
        },
        required: ["question", "answer", "follow_ups"],
        additionalProperties: false,
      },
    },
  },
  required: ["follow_up_questions"],
  additionalProperties: false,
};

function selectNine(candidates, history) {
  const selected = [];
  for (const category of REQUIRED_CATEGORIES) {
    const pool = candidates.filter((c) => c.category === category);
    let pick = pool.find((c) => !isDuplicate(c, selected, history));
    if (!pick && category === "랜덤") {
      pick = candidates.find((c) => !isDuplicate(c, selected, history));
    }
    if (!pick) {
      console.error(`[select] unusable category=${category} pool=${pool.length}`);
      for (const c of pool) {
        console.error(`  - ${c.topic} :: ${c.question}`);
      }
      throw new Error(`No usable candidate for category: ${category}`);
    }
    selected.push(pick);
  }
  return selected;
}

function hasCategoryQuota(candidates) {
  if (!Array.isArray(candidates) || candidates.length !== 36) return false;
  const counts = Object.fromEntries(REQUIRED_CATEGORIES.map((c) => [c, 0]));
  for (const c of candidates) {
    if (Object.prototype.hasOwnProperty.call(counts, c.category)) counts[c.category] += 1;
  }
  return REQUIRED_CATEGORIES.every((category) => counts[category] === 4);
}

function buildTree(selected) {
  const byCategory = Object.fromEntries(selected.map((c) => [c.category, c]));
  return [
    {
      question: byCategory["인물 배경"].question,
      follow_ups: [
        { question: byCategory["지명 정보"].question },
        { question: byCategory["본문 디테일"].question },
      ],
    },
    {
      question: byCategory["주석형/본문관찰"].question,
      follow_ups: [
        { question: byCategory["문화·관습"].question },
        { question: byCategory["신학/해석 견해"].question },
      ],
    },
    {
      question: byCategory["연결 질문"].question,
      follow_ups: [
        { question: byCategory["어원·유래"].question },
        { question: byCategory["랜덤"].question },
      ],
    },
  ];
}

function validateFinal(items, selected) {
  const qs = flattenFollowups(items);
  if (qs.length !== 9) throw new Error(`final question count ${qs.length}`);
  for (let i = 0; i < qs.length; i += 1) {
    for (let j = 0; j < i; j += 1) {
      if (sameContext(qs[i], qs[j])) throw new Error(`duplicate final: ${qs[j]} <-> ${qs[i]}`);
    }
  }
  const selectedQuestions = new Set(selected.map((c) => c.question));
  for (const q of qs) {
    if (!selectedQuestions.has(q)) throw new Error(`final changed question: ${q}`);
    if (/[왜]|이유/.test(q)) throw new Error(`question wording is too causal: ${q}`);
    if (/브에롯.*깃다임|깃다임.*브에롯/.test(q)) throw new Error(`forbidden repeated topic: ${q}`);
  }
  const answers = [];
  for (const main of items) {
    answers.push(main.answer || "");
    for (const tail of main.follow_ups || []) answers.push(tail.answer || "");
  }
  for (const answer of answers) {
    if (!answer.includes("\n\n")) throw new Error(`answer is not two paragraphs: ${answer.slice(0, 40)}`);
    if (answer.length < 180) throw new Error(`answer too short: ${answer.slice(0, 40)}`);
  }
}

async function main() {
  const qt = readJson(`data/qt/${DATE}.json`);
  const deep = readJson(`data/deep_dive/${DATE}.json`);
  const kbPath = `data/reference/${qt.book_name}.json`;
  const kb = fs.existsSync(path.join(ROOT, kbPath)) ? sliceKb(readJson(kbPath), qt) : null;
  const history = loadHistory(qt);
  const basePayload = {
    date: DATE,
    scripture_ref: qt.scripture_ref,
    title: qt.title,
    body_text: bodyText(qt),
    oryun_questions: qt.oryun_questions || [],
    kb,
    existing_same_book_questions: history,
    already_used_in_5step: {
      장면: deep["장면"] || "",
      질문: deep["질문"] || "",
      맥락: deep["맥락"] || "",
      통찰: deep["통찰"] || "",
      연결: deep["연결"] || "",
    },
  };

  const candidateSystem = `너는 한국 일반 개신교 큐티 콘텐츠의 STEP 2 '떠오르는 질문' 후보 생성자다.
오늘 본문과 KB에 근거해 후보 질문만 정확히 36개 만든다. 답변은 만들지 않는다.
각 후보는 category/topic/source/group_hint를 반드시 붙인다.
category는 지정 enum 중 하나만 쓴다.
카테고리별 후보 수는 정확히 4개씩이다. 9개 카테고리 x 4개 = 총 36개다.
주석형/본문관찰 4개, 지명 정보 4개, 어원·유래 4개, 인물 배경 4개, 문화·관습 4개, 신학/해석 견해 4개, 본문 디테일 4개, 연결 질문 4개, 랜덤 4개를 반드시 만든다.
KB에 없는 내용을 단정하지 말고, 본문 직접 관찰로 가능한 후보는 source에 본문 절을 적는다.
기존 질문 목록과 같은 소재, 같은 맥락, 같은 지명-행동 조합은 금지한다.
같은 후보 풀 안에서도 topic이 겹치면 안 된다.
'브에롯 사람들이 깃다임으로 도망/이주/피신한 이유' 소재는 이미 중복 사고가 난 소재이므로 절대 만들지 말라.
질문 문장에 '왜', '이유'를 쓰지 않는다. 원인형 질문 대신 대상을 직접 묻는 제목형으로 쓴다.
질문은 짧고 구체적으로, 답을 미리 말하지 않는 제목형으로 쓴다.`;

  let candidates = [];
  let selected = null;
  let lastSelectError = null;
  for (let attempt = 1; attempt <= 4; attempt += 1) {
    const candidateOut = await chat({
      system: candidateSystem,
      payload: { ...basePayload, required_candidate_count: 36, attempt },
      schema: candidateSchema,
      schemaName: "candidate_pool",
      temperature: 0.75,
      maxTokens: 7500,
    });
    candidates = candidateOut.candidates || [];
    const counts = Object.fromEntries(REQUIRED_CATEGORIES.map((category) => [
      category,
      candidates.filter((c) => c.category === category).length,
    ]));
    console.log(`[candidate] attempt=${attempt} count=${candidates.length} counts=${JSON.stringify(counts)}`);
    if (!hasCategoryQuota(candidates)) continue;
    try {
      selected = selectNine(candidates, history);
      lastSelectError = null;
      break;
    } catch (err) {
      lastSelectError = err;
      console.log(`[select] attempt=${attempt} failed: ${err.message}`);
    }
  }
  if (!selected) {
    throw lastSelectError || new Error(`candidate quota failed: count=${candidates?.length}`);
  }
  const tree = buildTree(selected);

  const finalSystem = `너는 한국 일반 개신교 큐티 콘텐츠의 STEP 2 답변 작성자다.
입력의 구성에 있는 질문 9개를 글자 하나도 바꾸지 말고 그대로 사용한다.
메인 3개, 각 꼬리 2개 구조도 유지한다.
답변은 각 질문마다 반드시 2문단이며, 두 문단 사이에 빈 줄 하나를 넣는다.
각 답변은 220~450자 정도로 쓴다. 한 문단 답변은 실패다.
첫 문단은 본문/KB 근거, 둘째 문단은 묵상자가 이해할 배경과 의미를 설명한다.
근거가 불확실한 역사 추정은 '~로 보입니다', '~가능성이 있습니다'처럼 조심스럽게 쓴다.
없는 정보를 지어내지 말고, 신학적으로 한쪽 교단 색채로 단정하지 않는다.`;

  let finalOut = null;
  let lastFinalError = null;
  for (let attempt = 1; attempt <= 4; attempt += 1) {
    try {
      finalOut = await chat({
        system: finalSystem,
        payload: { ...basePayload, 구성: tree, selected_candidates: selected, attempt },
        schema: finalSchema,
        schemaName: "follow_up_questions_response",
        temperature: 0.45,
        maxTokens: 9000,
      });
      validateFinal(finalOut.follow_up_questions, selected);
      console.log(`[final] attempt=${attempt} ok`);
      break;
    } catch (err) {
      lastFinalError = err;
      console.log(`[final] attempt=${attempt} failed: ${err.message}`);
      finalOut = null;
    }
  }
  if (!finalOut) throw lastFinalError || new Error("final generation failed");

  deep.follow_up_questions = finalOut.follow_up_questions;
  deep._followup_candidate_pool_count = 36;
  deep._followup_generation_method = "36-candidate-pool-select-then-compose";
  deep._followup_category_map = selected.map((c) => ({
    category: c.category,
    topic: c.topic,
    question: c.question,
    source: c.source,
    group_hint: c.group_hint,
  }));
  deep._followup_updated = new Date().toISOString();
  writeJson(`data/deep_dive/${DATE}.json`, deep);

  console.log(JSON.stringify({
    date: DATE,
    candidates: candidates.length,
    selected: selected.map((c) => `${c.category}:${c.topic}`),
  }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
