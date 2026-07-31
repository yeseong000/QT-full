const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const DATE = "2026-07-09";
const MODEL = "gpt-4o";

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
if (!API_KEY) throw new Error("OPENAI_API_KEY is missing");

function readJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), "utf8"));
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

async function chat({ system, payload, schema, schemaName, temperature = 0.1, maxTokens = 4000 }) {
  const resp = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${API_KEY}` },
    body: JSON.stringify({
      model: MODEL,
      messages: [
        { role: "system", content: system },
        { role: "user", content: JSON.stringify(payload) },
      ],
      temperature,
      max_tokens: maxTokens,
      response_format: { type: "json_schema", json_schema: { name: schemaName, strict: true, schema } },
    }),
  });
  if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
  const json = await resp.json();
  return JSON.parse(json.choices[0].message.content);
}

const verdictSchema = {
  type: "object",
  properties: {
    findings: {
      type: "array",
      items: {
        type: "object",
        properties: {
          slot: { type: "string" },
          question: { type: "string" },
          grounding: { type: "string", enum: ["KB_또는_본문_근거있음", "본문에서_직접_확인가능", "추정성_표현으로_완화됨", "근거없이_단정함"] },
          unsupported_claims: { type: "array", items: { type: "string" } },
          note: { type: "string" },
        },
        required: ["slot", "question", "grounding", "unsupported_claims", "note"],
        additionalProperties: false,
      },
    },
    overall_verdict: { type: "string", enum: ["신뢰가능", "부분수정필요", "재검토필요"] },
    overall_note: { type: "string" },
  },
  required: ["findings", "overall_verdict", "overall_note"],
  additionalProperties: false,
};

const system = `너는 한국 개신교 큐티 콘텐츠의 신학·사실 팩트체커다. 생성 과정에 관여하지 않았고, 결과만 받아 독립적으로 검수한다.
입력으로 그날 본문 전체, 그날 KB(있으면), 그리고 이미 완성된 9개 질문+답변을 받는다.
각 답변을 문장 단위로 뜯어, 본문에 직접 있는 사실인지 / KB에 있는 사실인지 / 본문·KB 어디에도 없는데 단정적으로 말한 추정(연대·지명 현대위치·원어 뜻·인물관계 등)인지 구분한다.
'~로 보입니다/~가능성이 있습니다'처럼 완화된 추정은 근거없는 단정보다는 낫지만, 그래도 KB나 본문에 실마리가 전혀 없다면 unsupported_claims에 적는다.
없는 사실을 지어내 단정한 문장이 있으면 grounding을 '근거없이_단정함'으로 표시하고 unsupported_claims에 정확히 그 문장을 인용한다.
너그럽게 봐주지 말고, 의심스러우면 근거를 요구하는 태도로 검수한다.`;

async function main() {
  const qt = readJson(`data/qt/${DATE}.json`);
  const deep = readJson(`data/deep_dive/${DATE}.json`);
  const kbPath = `data/reference/${qt.book_name}.json`;
  const kb = fs.existsSync(path.join(ROOT, kbPath)) ? sliceKb(readJson(kbPath), qt) : null;

  const slots = [];
  (deep.follow_up_questions || []).forEach((m, mi) => {
    slots.push({ slot: `메인${mi + 1}`, question: m.question, answer: m.answer });
    (m.follow_ups || []).forEach((t, ti) => {
      slots.push({ slot: `꼬리${mi + 1}-${ti + 1}`, question: t.question, answer: t.answer });
    });
  });

  const payload = {
    본문_참조: qt.scripture_ref,
    본문_내용: bodyText(qt),
    KB: kb,
    검수_대상: slots,
  };

  const out = await chat({ system, payload, schema: verdictSchema, schemaName: "grounding_check", maxTokens: 5000 });
  console.log(JSON.stringify(out, null, 2));

  const outPath = path.join(ROOT, "scripts", "_kb_grounding_report_0709.json");
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2), "utf8");
  console.log(`\n저장: ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
