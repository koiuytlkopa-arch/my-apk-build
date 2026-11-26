// Nexus Learn v7: توجيه متعلّم + دروس من الأخطاء + مولّد بيانات تدريب (تقطير) + تنفيذ كود معزول بمهلة
const B = () => S.brain || (S.brain = { st: {}, les: [], data: [] });
const RED = /(sk-[\w-]{16,}|AIza[\w-]{30,}|gsk_\w{20,}|nvapi-[\w-]{20,}|csk-\w{20,}|Bearer\s+[\w.-]{20,})/g;
const pend = {};
Object.assign(Brain, {
  used: new Set(), intent: 'fast',
  // يسجّل نجاح/فشل كل مزوّد لكل نوع مهمة (يتعلّم من التجربة)
  note(id, intent, ok, ms, m) {
    const k = id + ':' + intent, s = B().st[k] = B().st[k] || { o: 0, f: 0, ms: 0 };
    if (ok) { s.o++; s.ms = s.ms ? Math.round(s.ms * .7 + ms * .3) : ms; this.used.add(id + '/' + m); } else s.f++;
    if (s.o + s.f > 40) { s.o = Math.round(s.o / 2); s.f = Math.round(s.f / 2); }
    sv();
  },
  // ترتيب بحسب نسبة النجاح والسرعة + استكشاف 10% لتجربة بدائل
  rank(L, intent) {
    const sc = p => { const s = B().st[p.id + ':' + intent] || { o: 0, f: 0, ms: 0 }; return (s.o + 1) / (s.o + s.f + 2) * 10 + (ORDER[intent].length - ORDER[intent].indexOf(p.id)) * .5 - Math.min(s.ms, 20000) / 10000; };
    L = L.slice().sort((a, b) => sc(b) - sc(a));
    if (L.length > 1 && Math.random() < .1) [L[0], L[1]] = [L[1], L[0]];
    return L;
  },
  // خطأ أداة ثم نجاحها لاحقاً = درس يُحقن في التعليمات
  observe(n, a, r, ok) {
    const L = B().les;
    if (!ok) { pend[n] = String(r.error).slice(0, 90); return; }
    if (pend[n]) { L.push({ t: n, e: pend[n], a: JSON.stringify(a).slice(0, 110) }); delete pend[n]; if (L.length > 12) L.shift(); sv(); }
  },
  lessons() { const L = B().les.slice(-6); return L.length ? 'دروس مكتسبة من أخطاء سابقة (طبّقها):\n' + L.map(x => `- ${x.t}: الخطأ «${x.e}» ← نجح لاحقاً بـ ${x.a}`).join('\n') : ''; },
  // يحفظ المهام الناجحة فقط كعيّنات تدريب (بعد إخفاء المفاتيح)
  record(i0) {
    if (S.cfg.learn == 'off') return;
    const h = H().slice(i0), last = h[h.length - 1], lt = [...h].reverse().find(x => x.tool);
    if (h.length < 2 || !last || last.role != 'assistant' || last.text.length < 20 || /<tool>/.test(last.text) || (lt && /"error"/.test(lt.text))) return;
    const m = h.map(x => ({ role: x.role, content: x.text.replace(RED, '[REDACTED]').slice(0, 6000) }));
    if (JSON.stringify(m).length > 40000) return;
    B().data.push({ t: Date.now(), p: [...this.used], i: this.intent, m }); this.used.clear();
    if (B().data.length > 200) B().data.shift(); sv();
  },
  exportData() { return B().data.map(d => JSON.stringify({ messages: d.m, meta: { providers: d.p, intent: d.i } })).join('\n'); },
  stats() {
    const o = PROVIDERS.map(p => ['fast', 'strong'].map(i => { const s = B().st[p.id + ':' + i]; return s ? `${p.id}/${i}: ${s.o}✓ ${s.f}✗ ${s.ms}ms` : ''; }).filter(Boolean).join(' | ')).filter(Boolean);
    return o.join('\n') + `\nدروس: ${B().les.length} · عيّنات تدريب: ${B().data.length}`;
  }
});
// تنفيذ JS في Worker: مهلة تقتل الحلقات اللانهائية، وبلا وصول لـ IndexedDB
const runIso = (code, ms = 10000) => new Promise((res, rej) => {
  const src = `for(const k of ['indexedDB','caches'])try{Object.defineProperty(self,k,{value:undefined})}catch(e){}
onmessage=async e=>{const L=[],f=(...x)=>L.push(x.map(v=>typeof v=='object'?JSON.stringify(v):v).join(' '));try{const r=await new (Object.getPrototypeOf(async function(){}).constructor)('console','fs','mem',e.data.code)({log:f,error:f,warn:f},e.data.fs,e.data.mem);postMessage({logs:L.join('\\n').slice(0,5000),result:r===undefined?null:String(JSON.stringify(r)).slice(0,4000)})}catch(x){postMessage({err:String(x)})}}`;
  const w = new Worker(URL.createObjectURL(new Blob([src], { type: 'text/javascript' })));
  const to = setTimeout(() => { w.terminate(); rej('انتهت المهلة (' + ms / 1000 + 'ث): الكود عالق أو ثقيل'); }, ms);
  w.onmessage = e => { clearTimeout(to); w.terminate(); e.data.err ? rej(e.data.err) : res(e.data); };
  w.onerror = e => { clearTimeout(to); w.terminate(); rej(String(e.message || 'خطأ')); };
  w.postMessage({ code, fs: Object.fromEntries(Object.entries(fs).filter(([, v]) => !isBin(v))), mem });
});
