// Nexus Brain v6: سجل المزوّدين + توجيه حسب النية + مراقبة الصحة + تبديل تلقائي
const PROVIDERS = [
  { id: 'custom', n: 'خادمك الخاص (Ollama / llama.cpp / vLLM)', key: 0, custom: 1, get base() { return S.cfg.cbase || ''; }, get fixed() { return S.cfg.cmodel ? [S.cfg.cmodel] : null; }, pref: [/./] },
  { id: 'cerebras', n: 'Cerebras (الأسرع)', base: 'https://api.cerebras.ai/v1', key: 1, url: 'cloud.cerebras.ai', pref: [/gpt-oss-120b/i, /qwen/i, /llama/i] },
  { id: 'groq', n: 'Groq (سريع)', base: 'https://api.groq.com/openai/v1', key: 1, url: 'console.groq.com', pref: [/gpt-oss-120b/i, /qwen/i, /llama-?(3\.3|4)/i, /gpt-oss/i] },
  { id: 'gemini', n: 'Gemini (الأقوى)', base: 'https://generativelanguage.googleapis.com/v1beta/openai', key: 1, url: 'aistudio.google.com', pref: [/gemini-3\.5-flash$/i, /gemini-3.*flash/i, /gemini-2\.5-flash$/i] },
  { id: 'nvidia', n: 'NVIDIA NIM (+120 نموذج)', base: 'https://integrate.api.nvidia.com/v1', key: 1, url: 'build.nvidia.com', pref: [/deepseek/i, /gpt-oss-120b/i, /qwen/i, /llama-3\.3/i, /nemotron/i] },
  { id: 'openrouter', n: 'OpenRouter (نماذج :free)', base: 'https://openrouter.ai/api/v1', key: 1, url: 'openrouter.ai', free: /:free$/, pref: [/gpt-oss-120b/i, /deepseek/i, /qwen/i, /llama-3\.3/i, /gemma/i] },
  { id: 'llm7', n: 'LLM7 (بلا مفتاح)', base: LLM7, key: 0, pref: PREF },
  { id: 'device', n: 'النموذج المحلي (جهازك)', key: 0, local: 1, fixed: ['device'] },
  { id: 'pollinations', n: 'Pollinations (احتياط)', base: POLL, key: 0, fixed: ['openai'] }
];
// fast: خطوات الأدوات السريعة — strong: التخطيط والبرمجة وإصلاح الأخطاء
const ORDER = {
  fast: ['custom', 'cerebras', 'groq', 'nvidia', 'gemini', 'openrouter', 'llm7', 'pollinations', 'device'],
  strong: ['custom', 'gemini', 'nvidia', 'openrouter', 'cerebras', 'groq', 'llm7', 'pollinations', 'device']
};
const BH = {}, BM = {}; // صحة المزوّدين وكاش النماذج (بالذاكرة)
const bKey = p => (p.key ? (S.cfg.keys || {})[p.id] || '' : p.id == 'llm7' ? S.cfg.llm7 || 'unused' : p.id == 'custom' ? (S.cfg.keys || {}).custom || '' : '');

async function bModels(p) {
  if (BM[p.id]) return BM[p.id];
  if (p.fixed) return (BM[p.id] = p.fixed);
  const [r, j] = await post(p.base + '/models', { method: 'GET', headers: p.key ? { Authorization: 'Bearer ' + bKey(p) } : {} }, 15000);
  if (r.status == 401 || r.status == 403) throw Object.assign(new Error('المفتاح مرفوض'), { status: r.status });
  let ids = (j.data || j.models || (Array.isArray(j) ? j : [])).map(x => String(x.id || x.name || x).replace(/^models\//, '')).filter(x => !SKIP.test(x) && (!p.free || p.free.test(x)));
  const rank = id => { const i = p.pref.findIndex(q => q.test(id)); return i < 0 ? 99 : i; };
  ids.sort((a, b) => rank(a) - rank(b));
  ids = ids.filter(x => rank(x) < 99).concat(ids.filter(x => rank(x) == 99)).slice(0, 3);
  if (!ids.length) throw new Error('لا نماذج متاحة');
  return (BM[p.id] = ids);
}

const Brain = {
  list: () => PROVIDERS,
  reset() { for (const k in BM) delete BM[k]; for (const k in BH) delete BH[k]; },
  async chat(msgs, intent = 'fast') {
    Brain.intent = intent; const now = Date.now(), alive = id => { const p = PROVIDERS.find(x => x.id == id); return p && (!p.key || bKey(p)) && (!p.local || Dev.ready) && (!p.custom || p.base) && !(BH[id] || {}).off ? p : null; };
    let L = ORDER[intent].map(alive).filter(Boolean);
    const ready = L.filter(p => ((BH[p.id] || {}).cd || 0) <= now); if (ready.length) L = ready; if (!navigator.onLine) L = L.filter(p => p.local); L = Brain.rank(L, intent);
    let err;
    for (const p of L.slice(0, 5)) {
      const h = BH[p.id] = BH[p.id] || { f: 0, cd: 0, ms: 0 };
      let models; try { models = await bModels(p); } catch (e) { if (e.name == 'AbortError') throw e; err = e; Brain.fail(p, h, e); continue; }
      for (const m of models.slice(0, 2)) {
        const t0 = Date.now();
        try {
          const t = p.local ? await Dev.chat(msgs) : await oai(p.base, bKey(p), m, msgs, p.id == 'pollinations' ? 60000 : 45000);
          h.f = 0; h.ms = Math.round((h.ms || Date.now() - t0) * .6 + (Date.now() - t0) * .4); lastUsed = p.id + '/' + m; Brain.note(p.id, intent, 1, Date.now() - t0, m); setStatus(); return t;
        } catch (e) {
          if (e.name == 'AbortError') throw e; err = e;
          if (Brain.fail(p, h, e, m)) break;
        }
      }
    }
    throw err || new Error('تعذر الوصول لأي مزوّد');
  },
  // يسجّل الفشل؛ يرجع true إن كان يجب ترك المزوّد كله (مفتاح مرفوض/ضغط)
  fail(p, h, e, m) {
    const s = e.status; if (s != 429 && s != 401 && s != 403) Brain.note(p.id, Brain.intent, 0);
    if (s == 401 || s == 403) { h.off = 'مفتاح مرفوض'; chip('🔑 ' + p.id + ': المفتاح مرفوض — عطّلته'); return true; }
    if (s == 429) { h.cd = Date.now() + 60000; chip('⏳ ' + p.id + ' ضغط — تبديل المزوّد'); return true; }
    h.f++; h.cd = Date.now() + Math.min(300000, 5000 * 2 ** h.f); chip('↪ ' + p.id + (m ? '/' + m : '') + ': ' + String(e.message).slice(0, 40)); return false;
  }
};
// يحدد نية الخطوة الحالية: تخطيط/برمجة/خطأ → strong، غير ذلك → fast
function intentNow() {
  const l = H()[H().length - 1];
  if (l.tool) return /"error"/.test(l.text) ? 'strong' : 'fast';
  return l.text.length > 120 || /كود|برمج|لعبة|تطبيق|خطة|code|html|apk|app/i.test(l.text) ? 'strong' : 'fast';
}
// واجهة مفاتيح المزوّدين في الإعدادات
function brainUI() {
  const g = $('g-brain'); g.innerHTML = '<label>مفاتيح المزوّدين (اختيارية — كل مفتاح يضيف سرعة وحدّاً أعلى)</label>';
  PROVIDERS.filter(p => p.key).forEach(p => {
    const i = document.createElement('input'); i.type = 'password'; i.dir = 'ltr'; i.dataset.pk = p.id; i.value = (S.cfg.keys || {})[p.id] || ''; i.placeholder = p.n + ' — ' + p.url;
    g.appendChild(i);
  });
  const add = (ph, id, pk) => { const i = document.createElement('input'); i.dir = 'ltr'; i.placeholder = ph; if (pk) { i.type = 'password'; i.dataset.pk = pk; i.value = (S.cfg.keys || {})[pk] || ''; } else { i.id = id; i.value = S.cfg[id] || ''; } g.appendChild(i); };
  g.insertAdjacentHTML('beforeend', '<label>خادمك الخاص (متوافق مع OpenAI): عنوان https، نموذج، مفتاح اختياري</label>');
  add('https://your-server/v1', 'cbase'); add('اسم النموذج (اختياري)', 'cmodel'); add('مفتاح الخادم (اختياري)', '', 'custom');
  g.insertAdjacentHTML('beforeend', '<label>مفاتيح البحث (اختيارية — نتائج أدق)</label>');
  add('Tavily — tavily.com', '', 'tavily'); add('Brave Search — brave.com/search/api', '', 'brave');
}
