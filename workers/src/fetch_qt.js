// 오륜교회 주만나 페이지를 가져와 QT JSON으로 변환합니다.
// scripts/fetch_qt.py 의 1:1 JS 포팅입니다.

import * as cheerio from 'cheerio';
import { extractCookies, log, nowKstIso, sleep, todayKst } from './util.js';

const URL = 'https://oryun.org/life/?menu=248';
const MAIN_URL = 'https://oryun.org/';

const HEADERS = {
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ' +
    'AppleWebKit/537.36 (KHTML, like Gecko) ' +
    'Chrome/120.0.0.0 Safari/537.36',
  'Accept':
    'text/html,application/xhtml+xml,application/xml;q=0.9,' +
    'image/avif,image/webp,image/apng,*/*;q=0.8',
  'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
  'Accept-Encoding': 'gzip, deflate, br',
  'Connection': 'keep-alive',
  'Upgrade-Insecure-Requests': '1',
  'Sec-Fetch-Dest': 'document',
  'Sec-Fetch-Mode': 'navigate',
  'Sec-Fetch-Site': 'none',
};

// 페이지 HTML을 가져온다. 실패 시 재시도.
async function fetchPage(retries = 3) {
  // 메인 페이지 선방문 (쿠키/세션 획득)
  log('INFO', '메인 페이지 방문 중...');
  let cookies = '';
  try {
    const mainRes = await fetch(MAIN_URL, { headers: HEADERS });
    cookies = extractCookies(mainRes);
  } catch (e) {
    log('WARN', `메인 페이지 접근 실패 (무시하고 계속): ${e.message}`);
  }

  const reqHeaders = { ...HEADERS };
  if (cookies) reqHeaders['Cookie'] = cookies;

  let lastErr = null;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      log('INFO', `QT 페이지 요청 중 (시도 ${attempt}/${retries})...`);
      const res = await fetch(URL, { headers: reqHeaders });
      if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
      const text = await res.text();
      log('OK', `응답 수신 완료 (${text.length.toLocaleString()} bytes)`);
      return text;
    } catch (e) {
      lastErr = e;
      log('WARN', `시도 ${attempt} 실패: ${e.message}`);
      if (attempt < retries) {
        const wait = 2 ** attempt;
        log('INFO', `${wait}초 후 재시도...`);
        await sleep(wait * 1000);
      }
    }
  }

  throw new Error(`페이지 요청이 ${retries}회 모두 실패했습니다: ${lastErr?.message}`);
}

// '회복으로 나아가라 룻기 1:15-22' → ['회복으로 나아가라', '룻기 1:15-22']
function splitTitleAndRef(line) {
  const pattern = /^(.+?)\s+([가-힣]+(?:상|하)?)\s+(\d+):(\d+)(?:[-~](\d+))?$/;
  const m = pattern.exec(line.trim());
  if (!m) {
    log('WARN', `제목/구절 파싱 실패: ${line}`);
    return [line.trim(), ''];
  }
  const [, title, book, chapter, vStart, vEnd] = m;
  let ref = `${book} ${chapter}:${vStart}`;
  if (vEnd) ref += `-${vEnd}`;
  return [title.trim(), ref];
}

// '룻기 1:15-22' → {book, chapter, start, end}
function parseScriptureRef(ref) {
  const m = /([가-힣]+(?:상|하)?)\s+(\d+):(\d+)(?:[-~](\d+))?/.exec(ref);
  if (!m) return { book: '', chapter: 0, start: 0, end: 0 };
  return {
    book: m[1],
    chapter: parseInt(m[2], 10),
    start: parseInt(m[3], 10),
    end: m[4] ? parseInt(m[4], 10) : parseInt(m[3], 10),
  };
}

// cheerio 노드의 텍스트를 ' ' 구분자 + 공백 정리 형태로 추출 (BeautifulSoup get_text(' ', strip=True) 흉내)
function getTextSpaced($, el) {
  const raw = $(el).text();
  return raw.replace(/\s+/g, ' ').trim();
}

// 한글 본문만. 영문 구분선 이후는 스킵.
function extractVerses($, start, end) {
  const verses = [];
  let koreanDone = false;

  $('li').each((_, li) => {
    const text = getTextSpaced($, li);

    if (text === '-' || text === '--' || text === '—') {
      koreanDone = true;
      return;
    }
    if (koreanDone) return;

    const m = /^(\d+)\s+(.+)$/.exec(text);
    if (!m) return;

    const verseNum = parseInt(m[1], 10);
    const verseText = m[2].trim();

    if (verseNum < start || verseNum > end) return;

    if (verses.some((v) => v.number === verseNum)) return;

    if (!/[가-힣]/.test(verseText)) return;

    verses.push({ number: verseNum, text: verseText });
  });

  verses.sort((a, b) => a.number - b.number);
  return verses;
}

function extractQuestions($) {
  const questions = [];
  $('dt, dd, p').each((_, el) => {
    const text = getTextSpaced($, el);
    if (text.includes('오늘의 만나')) {
      const idx = text.indexOf('오늘의 만나');
      let q = text.slice(idx + '오늘의 만나'.length).trim();
      if (q) {
        q = q.replace(/\s*\d+\s*\/\s*\d+\s*$/, '').trim();
        q = q.replace(/\s*(등록|취소)\s*$/, '').trim();
        if (q && !questions.includes(q) && q.length > 5) {
          questions.push(q);
        }
      }
    }
  });
  return questions;
}

function findFirstVerseLi($) {
  let firstVerseLi = null;
  $('li').each((_, li) => {
    const text = $(li).text().trim();
    if (/^\d+\s/.test(text)) {
      firstVerseLi = li;
      return false; // break
    }
  });
  return firstVerseLi;
}

// firstVerseLi 직전(상위 트리 포함)의 p/h2/h3/h4/dt/dd 중 가장 가까운 것
function findPreviousMeta($, firstVerseLi) {
  if (!firstVerseLi) return null;

  // cheerio는 prev() / parents() 위주로 작동하므로
  // 전체 문서 순서대로 후보를 모은 뒤 firstVerseLi 직전의 마지막 후보를 취합니다.
  const candidates = [];
  $('p, h2, h3, h4, dt, dd, li').each((_, el) => {
    candidates.push(el);
  });

  let prev = null;
  for (const el of candidates) {
    if (el === firstVerseLi) break;
    const tag = el.tagName || el.name;
    if (['p', 'h2', 'h3', 'h4', 'dt', 'dd'].includes(tag)) {
      prev = el;
    }
  }
  return prev;
}

// HTML → QT 데이터 dict
function parseQt(html) {
  const $ = cheerio.load(html);

  // 날짜 레이블 찾기 (dt 중 'NN.NN' 으로 시작)
  let dateLabel = null;
  let titleLine = null;

  $('dt').each((_, dt) => {
    const text = $(dt).text().trim();
    if (/^\d{2}\.\d{2}/.test(text)) {
      dateLabel = text;
      // 형제 dd
      const dd = $(dt).next('dd');
      if (dd.length) {
        titleLine = dd.text().replace(/\s+/g, ' ').trim();
      }
      return false; // break
    }
  });

  if (!dateLabel) {
    throw new Error('날짜 레이블을 찾을 수 없습니다. 페이지 구조가 바뀌었을 수 있어요.');
  }
  log('OK', `날짜 레이블: ${dateLabel}`);

  if (!titleLine) {
    throw new Error('제목 라인을 찾을 수 없습니다.');
  }

  const [title, scriptureRef] = splitTitleAndRef(titleLine);
  log('OK', `제목: ${title}`);
  log('OK', `구절: ${scriptureRef}`);

  const refParsed = parseScriptureRef(scriptureRef);

  // 부제
  let subtitle = '';
  const firstVerseLi = findFirstVerseLi($);
  if (firstVerseLi) {
    const prev = findPreviousMeta($, firstVerseLi);
    if (prev) {
      const candidate = $(prev).text().trim();
      if (
        candidate &&
        candidate !== titleLine &&
        candidate.length > 5 &&
        candidate.length < 50 &&
        !candidate.includes('오늘의') &&
        !candidate.includes('큐티') &&
        !candidate.includes('관련문의')
      ) {
        subtitle = candidate;
      }
    }
  }
  log('INFO', `부제: ${subtitle || '(없음)'}`);

  // 구절
  const verses = extractVerses($, refParsed.start, refParsed.end);
  log(verses.length ? 'OK' : 'WARN', `구절 추출: ${verses.length}절`);

  // 질문
  const questions = extractQuestions($);
  log('INFO', `질문 추출: ${questions.length}개`);

  return {
    date: todayKst(),
    date_label: dateLabel,
    title,
    subtitle,
    scripture_ref: scriptureRef,
    book_name: refParsed.book,
    chapter: refParsed.chapter,
    verses_start: refParsed.start,
    verses_end: refParsed.end,
    verses,
    oryun_questions: questions,
    full_chapter_verses: [],
    source_url: URL,
    fetched_at: nowKstIso(),
  };
}

function validateQt(data) {
  const warnings = [];
  if (!data.title) warnings.push('제목이 비어있음');
  if (!data.scripture_ref) warnings.push('성경 구절 범위가 비어있음');
  if (!data.verses?.length) {
    warnings.push('구절이 하나도 없음');
  } else if (data.verses_start && data.verses_end) {
    const expected = data.verses_end - data.verses_start + 1;
    const actual = data.verses.length;
    if (actual !== expected) {
      warnings.push(`구절 개수 불일치: 예상 ${expected}절, 실제 ${actual}절`);
    }
  }
  return warnings;
}

export async function fetchQt() {
  log('INFO', '='.repeat(50));
  log('INFO', '주만나 QT 크롤링 시작');
  log('INFO', '='.repeat(50));

  const html = await fetchPage();
  const data = parseQt(html);

  const warnings = validateQt(data);
  for (const w of warnings) log('WARN', w);

  log('INFO', '='.repeat(50));
  log('INFO', `제목:   ${data.title}`);
  log('INFO', `구절:   ${data.scripture_ref}`);
  log('INFO', `절 수:  ${data.verses.length}`);
  log('INFO', `질문:   ${data.oryun_questions.length}개`);
  log('INFO', '='.repeat(50));

  return data;
}
