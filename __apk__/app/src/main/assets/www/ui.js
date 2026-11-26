// الواجهة: عرض المحادثة، اللوحات، الإعدادات، القفل، التهيئة
let curPreview = { html: '', name: 'preview.html' };

// ---------- ماركداون مبسّط وآمن ----------
function md(src) {
  const blocks = [];
  let s = src.replace(/```([\w+-]*)[ \t]*\n?([\s\S]*?)```/g, (m, l, c) => { blocks.push({ l, c: c.replace(/\n$/, '') }); return '\u0000' + (blocks.length - 1) + '\u0000'; });
  s = esc(s)
    .replace(/^(#{1,3})\s+(.+)$/gm, (m, h, t) => `<h${h.length + 2}>${t}</h${h.length + 2}>`)
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const out = []; let list = null;
  for (const ln of s.split('\n')) {
    const m = ln.match(/^\s*([-*•]|\d+[.)])\s+(.*)$/);
    if (m) { const t = /\d/.test(m[1]) ? 'ol' : 'ul'; if (list && list != t) { out.push('</' + list + '>'); list = null; } if (!list) { out.push('<' + t + '>'); list = t; } out.push('<li>' + m[2] + '</li>'); }
    else { if (list) { out.push('</' + list + '>'); list = null; } out.push(/^<h\d/.test(ln) ? ln : ln + '<br>'); }
  }
  if (list) out.push('</' + list + '>');
  s = out.join('').replace(/(<br>){2,}/g, '<div class="sp"></div>').replace(/^(<br>|<div class="sp"><\/div>)+|(<br>|<div class="sp"><\/div>)+$/g, '');
  return { html: s.replace(/\u0000(\d+)\u0000/g, (m, i) => `<div class="cb" data-i="${i}"><div class="ch"><span>${esc(blocks[i].l || 'code')}</span><button data-act="copy">نسخ</button>${/^(html?|svg)$/i.test(blocks[i].l) ? '<button data-act="prev">معاينة</button>' : ''}</div><pre><code>${esc(blocks[i].c)}</code></pre></div>`), blocks };
}

// ---------- عناصر المحادثة ----------
const scroll = () => { const c = $('chat'); c.scrollTop = c.scrollHeight; };
function clearHero() { const h = $('chat').querySelector('.hero'); if (h) h.remove(); }
// يرسم نص الرد (ماركداون + كتل كود بأزرار نسخ/معاينة) داخل عنصر
function paint(d, t, live) {
  const r = md(t);
  d.innerHTML = r.html + (live ? '<span class="caret"></span>' : '');
  d.querySelectorAll('.cb').forEach(el => {
    const code = r.blocks[+el.dataset.i].c;
    const cp = el.querySelector('[data-act=copy]'); if (cp) cp.onclick = () => NX.copy(code).then(() => toast('تم النسخ'));
    const p = el.querySelector('[data-act=prev]'); if (p) p.onclick = () => showPreview(code, 'code.html');
  });
}
function add(c, t) {
  clearHero();
  const d = document.createElement('div'); d.className = 'm ' + c;
  if (c == 'a') paint(d, t); else d.textContent = t;
  $('chat').appendChild(d); scroll(); return d;
}
// تمرير ذكي: يتبع النص الجديد فقط إن كان المستخدم قريباً من الأسفل
function stick() { const c = $('chat'); if (c.scrollHeight - c.scrollTop - c.clientHeight < 160) c.scrollTop = c.scrollHeight; }
// رد يظهر حرفاً بحرف أثناء توليده؛ يُرسم مرة واحدة لكل إطار لتبقى الواجهة سلسة
function liveReply(ty) {
  let el = null, buf = '', raf = 0;
  const view = () => buf.replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '').replace(/<tool>[\s\S]*?(?:<\/tool>|$)/g, '').replace(/^\s+/, '');
  const drop = () => { if (raf) { cancelAnimationFrame(raf); raf = 0; } if (el) { el.remove(); el = null; } };
  const draw = () => {
    raf = 0; const v = view(); if (!v) return;
    if (!el) { clearHero(); el = document.createElement('div'); el.className = 'm a streaming'; $('chat').appendChild(el); if (ty) ty.remove(); }
    paint(el, v, true); stick();
  };
  return {
    reset() { buf = ''; drop(); },
    delta(s) { buf += s; if (!raf) raf = requestAnimationFrame(draw); },
    done() { drop(); }
  };
}
function chip(t) { clearHero(); const d = document.createElement('div'); d.className = 'c'; d.textContent = t; $('chat').appendChild(d); scroll(); }
function typing(on) { const d = document.createElement('div'); d.className = 'typing'; d.innerHTML = '<i></i><i></i><i></i>'; $('chat').appendChild(d); scroll(); return d; }
function toolCard(name, a) {
  clearHero();
  const d = document.createElement('div'); d.className = 'tc run';
  d.innerHTML = `<div class="h"><span class="ic">⟳</span><b>${esc(name)}</b><small>${esc(argHint(a))}</small></div><pre></pre>`;
  d.querySelector('pre').textContent = JSON.stringify(a, null, 1).slice(0, 600);
  d.onclick = () => d.classList.toggle('open'); $('chat').appendChild(d); scroll(); return d;
}
function toolDone(d, ok, ms, res) {
  d.classList.remove('run'); d.classList.add(ok ? 'ok' : 'er'); d.querySelector('.ic').textContent = ok ? '✓' : '✕';
  d.querySelector('.h').insertAdjacentHTML('beforeend', `<small>· ${ms}ms</small>`);
  d.querySelector('pre').textContent += '\n→ ' + (res || '').slice(0, 800); scroll();
}
function hero() {
  const ex = [
    ['🎮', 'اصنع لعبة ثعبان تفاعلية'],
    ['🔎', 'ابحث عن آخر أخبار الذكاء الاصطناعي ولخّصها'],
    ['🎬', 'اصنع فيديو قصير عن أهمية الوقت'],
    ['📱', 'ابنِ لي صفحة تطبيق بسيط وحوّله إلى APK']
  ];
  const h = document.createElement('div'); h.className = 'hero';
  h.innerHTML = `<svg class="big"><use href="#logo"/></svg><h2>أهلاً بك في Nexus</h2><p>وكيل ذكي ينفّذ المهام فعلياً: ملفات، بحث، كود، ألعاب، فيديو، وحتى تطبيقات.</p><div class="chips"></div>`;
  ex.forEach(([icon, x]) => {
    const b = document.createElement('button'); b.innerHTML = `<i></i><span></span>`;
    b.querySelector('i').textContent = icon; b.querySelector('span').textContent = x;
    b.onclick = () => { $('in').value = x; send(); };
    h.querySelector('.chips').appendChild(b);
  });
  $('chat').appendChild(h);
}
function rC() {
  $('chat').innerHTML = '';
  const hs = H();
  if (!hs.length) hero();
  hs.forEach(h => {
    if (h.tool) return;
    const v = h.text.replace(/<tool>[\s\S]*?(?:<\/tool>|$)/g, '').trim();
    if (v) add(h.role == 'user' ? 'u' : 'a', v);
    if (h.role == 'assistant') for (const k of parseCalls(h.text)) if (k.c) { const d = document.createElement('div'); d.className = 'tc ok'; d.innerHTML = `<div class="h"><span class="ic">✓</span><b>${esc(k.c.name)}</b><small>${esc(argHint(k.c.args))}</small></div>`; $('chat').appendChild(d); }
  });
  $('tt').textContent = cur().title; scroll();
}
function setStatus() {
  const p = S.cfg.prv, n = navigator.onLine;
  $('dot').style.background = p == 'local' ? '#a78bfa' : n ? 'var(--ok)' : 'var(--er)';
  const name = p == 'auto' ? 'مجاني · ' + (lastUsed || S.cfg.lastModel || 'تلقائي') : p == 'pro' ? 'Nexus Pro · متصل' : p == 'local' ? 'Nexus Core · محلي' : p == 'gemini' ? 'Gemini' : (S.cfg.model || 'مخصص');
  $('stx').textContent = (n || p == 'local' ? '' : 'بلا إنترنت · ') + name;
}

// ---------- لوحات ----------
function cl() { document.querySelectorAll('.pn').forEach(x => x.classList.remove('on')); }
const anyPanel = () => document.querySelector('.pn.on');
function showPreview(html, name) { curPreview = { html, name: name || 'preview.html' }; $('fr').srcdoc = html; $('pvt').textContent = 'المعاينة'; cl(); $('pv').classList.add('on'); }
function show(v) {
  document.querySelectorAll('.v').forEach(x => x.classList.toggle('on', x.id == 'v-' + v));
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.v == v));
  ({ files: rF, plan: rP, audit: rA })[v]?.();
}
const li = (h, f, cls = '') => { const d = document.createElement('div'); d.className = 'f ' + cls; d.innerHTML = h; if (f) d.onclick = f; return d; };
const empty = t => `<div class="empty">${t}</div>`;
function rF() {
  const l = $('fl'); l.innerHTML = '';
  Object.keys(fs).sort().forEach(p => l.appendChild(li(`<span>${isBin(fs[p]) ? '🎞' : isHtml(p) ? '🌐' : '📄'}</span><div class="x"><b class="ltr" style="display:block">${esc(p)}</b><small>${(fs[p].length / 1024).toFixed(1)} KB</small></div>`, () => isBin(fs[p]) ? NX.saveShare(p.split('/').pop(), fs[p]).catch(e => toast('⚠ ' + (e.message || e))) : ed(p))));
  if (!l.children.length) l.innerHTML = empty('لا ملفات بعد.<br>اطلب من Nexus أن يكتب أو يصنع شيئاً.');
}
function rP() {
  const l = $('pl'); l.innerHTML = '';
  todo.forEach(x => { const dn = /^\[x\]/i.test(String(x)); l.appendChild(li(`<span>${dn ? '✅' : '⬜'}</span><div class="x"><b>${esc(String(x).replace(/^\[[x ]\]\s*/i, ''))}</b></div>`, null, dn ? 'done' : '')); });
  if (!todo.length) l.innerHTML = empty('لا خطة نشطة.');
}
function rA() {
  const l = $('al'); l.innerHTML = '';
  S.audit.slice().reverse().forEach(x => l.appendChild(li(`<span>${x.ok ? '🟢' : '🔴'}</span><div class="x"><b>${esc(x.n)}</b> <small>${new Date(x.t).toLocaleTimeString()} · ${x.ms}ms</small><br><small class="ltr" style="display:block">${esc(x.a)}</small></div>`)));
  if (!S.audit.length) l.innerHTML = empty('لا عمليات بعد.');
}
function ed(p) { $('ep').textContent = p; $('et').value = fs[p]; cl(); $('pe').classList.add('on'); }
function rS() {
  const l = $('sl'); l.innerHTML = '';
  S.sessions.slice().reverse().forEach(s => {
    const w = document.createElement('div'); w.className = 'sess';
    w.appendChild(li(`<span>💬</span><div class="x"><b>${esc(s.title)}</b><br><small>${s.hist.filter(h => !h.tool).length} رسالة</small></div>`, () => { S.cur = s.id; allowAll = false; rC(); cl(); sv(); }));
    const d = document.createElement('button'); d.className = 'ib'; d.innerHTML = '<svg><use href="#i-trash"/></svg>';
    d.onclick = async () => { if (!(await confirmD('حذف المحادثة؟', s.title, 'حذف'))) return; S.sessions = S.sessions.filter(x => x.id != s.id); if (!S.sessions.length || !cur()) { newS(true); } else { S.cur = S.sessions[S.sessions.length - 1].id; } rS(); rC(); sv(); };
    w.appendChild(d); l.appendChild(w);
  });
}
function newS(silent) {
  const s = { id: Date.now() + Math.random(), title: 'محادثة جديدة', hist: [] }; S.sessions.push(s); S.cur = s.id; allowAll = false;
  if (!silent) { rC(); cl(); show('chat'); sv(); }
}

// ---------- إرسال ----------
async function send() {
  const t = $('in').value.trim(); if (!t || busy) return;
  if (S.cfg.prv == 'gemini' && !S.cfg.key || S.cfg.prv == 'openai' && !(S.cfg.key && S.cfg.model)) { toast('أدخل المفتاح/النموذج في الإعدادات'); openSettings(); return; }
  busy = true; stop = false; ctl = new AbortController(); setBtn(true); $('in').value = ''; grow();
  add('u', t); if (!H().length) cur().title = t.slice(0, 30); $('tt').textContent = cur().title; H().push({ role: 'user', text: t });
  try { await run(); } catch (e) { if (e.name != 'AbortError') add('a', '⚠ ' + e.message); else chip('⏹ أُوقفت المهمة'); }
  busy = false; setBtn(false); sv();
}
function setBtn(b) { const s = $('send'); s.classList.toggle('stop', b); s.innerHTML = `<svg><use href="#${b ? 'i-stop' : 'i-send'}"/></svg>`; }
function grow() { const e = $('in'); e.style.height = 'auto'; e.style.height = Math.min(e.scrollHeight, 140) + 'px'; }

// ---------- الإعدادات ----------
const FIELDS = ['prv', 'key', 'model', 'base', 'llm7', 'auto', 'role', 'theme', 'learn'];
function provUI() {
  const p = $('prv').value;
  $('g-auto').style.display = p == 'auto' ? '' : 'none'; $('g-brain').style.display = p == 'auto' ? '' : 'none'; $('privacy').style.display = p == 'auto' ? '' : 'none';
  $('g-key').style.display = p == 'openai' || p == 'gemini' ? '' : 'none';
  $('g-model').style.display = p == 'openai' || p == 'gemini' ? '' : 'none';
  $('g-base').style.display = p == 'openai' ? '' : 'none';
}
function openSettings() { FIELDS.forEach(k => $(k).value = S.cfg[k] || ''); brainUI(); $('g-stats').textContent = Brain.stats(); Dev.ui(); provUI(); cl(); $('ps').classList.add('on'); }
async function setPin() {
  if (S.cfg.pin) { if (!(await confirmD('إزالة القفل؟', 'سيفتح التطبيق بدون رمز.', 'إزالة'))) return; S.cfg.pin = null; sv(); toast('أُزيل القفل'); $('pin').textContent = '🔒 تعيين رمز قفل للتطبيق'; return; }
  const p = await promptD('رمز القفل', 'أرقام أو حروف (4 على الأقل)', '••••', 'password');
  if (!p) return; if (p.length < 4) return toast('4 أحرف على الأقل');
  const s = crypto.randomUUID(); S.cfg.pin = { s, h: await kd(p, s) }; sv(); toast('تم تفعيل القفل'); $('pin').textContent = '🔓 إزالة رمز القفل';
}
// ---------- القفل ----------
const kd = async (p, s) => { const E = new TextEncoder(); return [...new Uint8Array(await crypto.subtle.deriveBits({ name: 'PBKDF2', salt: E.encode(s), iterations: 150000, hash: 'SHA-256' }, await crypto.subtle.importKey('raw', E.encode(p), 'PBKDF2', false, ['deriveBits']), 256))].map(x => x.toString(16).padStart(2, '0')).join(''); };
function gate() { if (!S.cfg.pin) return; $('lock').classList.add('on'); setTimeout(() => $('lgp').focus(), 100); }
async function unlock() {
  const e = $('lge'); if (!S.cfg.pin) { $('lock').classList.remove('on'); return; }
  if (await kd($('lgp').value, S.cfg.pin.s) != S.cfg.pin.h) { e.textContent = 'رمز خاطئ'; return; }
  $('lgp').value = ''; e.textContent = ''; $('lock').classList.remove('on');
}

// ---------- ربط الأحداث ----------
function bind() {
  $('send').onclick = () => busy ? (stop = true, ctl.abort()) : send();
  $('in').addEventListener('input', grow);
  $('in').addEventListener('keydown', e => { if (e.key == 'Enter' && !e.shiftKey && !NX.native && innerWidth > 760) { e.preventDefault(); send(); } });
  $('bs').onclick = openSettings;
  $('bm').onclick = () => { rS(); cl(); $('pd').classList.add('on'); };
  $('ns').onclick = () => newS();
  $('bp').onclick = () => { const h = Object.keys(fs).filter(isHtml).pop(); if (h) showPreview(fs[h], h); else toast('لا يوجد ملف HTML للمعاينة'); };
  document.querySelectorAll('[data-close]').forEach(b => b.onclick = cl);
  document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => show(b.dataset.v));
  $('nf').onclick = async () => { const p = await promptD('ملف جديد', 'اسم الملف (مثال: index.html)', 'index.html'); if (p) { fs[p] = fs[p] || ''; sv(); rF(); ed(p); } };
  $('esv').onclick = () => { fs[$('ep').textContent] = $('et').value; sv(); cl(); toast('تم الحفظ'); rF(); };
  $('epv').onclick = () => showPreview($('et').value, $('ep').textContent);
  $('eps').onclick = () => NX.saveShare($('ep').textContent.split('/').pop(), $('et').value).catch(e => toast('⚠ ' + (e.message || e)));
  $('edl').onclick = async () => { if (await confirmD('حذف الملف؟', $('ep').textContent, 'حذف')) { delete fs[$('ep').textContent]; sv(); rF(); cl(); } };
  $('pvs').onclick = () => NX.saveShare(curPreview.name.split('/').pop(), curPreview.html).catch(e => toast('⚠ ' + (e.message || e)));
  $('prv').onchange = provUI;
  $('sv').onclick = () => { FIELDS.forEach(k => S.cfg[k] = $(k).value.trim()); if (!S.cfg.base) S.cfg.base = DEFAULT_CFG.base; S.cfg.keys = S.cfg.keys || {}; document.querySelectorAll('[data-pk]').forEach(i => S.cfg.keys[i.dataset.pk] = i.value.trim()); Brain.reset(); if ($('cbase')) { S.cfg.cbase = $('cbase').value.trim(); S.cfg.cmodel = $('cmodel').value.trim(); } document.body.dataset.t = S.cfg.theme; MODELS = null; setStatus(); cl(); sv(); toast('تم حفظ الإعدادات'); };
  $('pin').onclick = setPin; $('dv-go').onclick = Dev.install;
  $('erun').onclick = async () => { const p = $('ep').textContent, c = $('et').value; if (isHtml(p)) return showPreview(c, p); if (!/\.js$/i.test(p)) return toast('التشغيل لملفات html وjs فقط'); try { const r = await runIso(c); await dialog({ title: 'مخرجات التشغيل', body: (r.logs || '') + '\n→ ' + (r.result ?? ''), buttons: [{ id: 'ok', label: 'تم', cls: 'go' }] }); } catch (e) { toast('⚠ ' + e); } };
  $('exd').onclick = () => { const d = Brain.exportData(); if (!d) return toast('لا بيانات بعد — استخدم التطبيق أولاً'); NX.saveShare('nexus-train.jsonl', d).catch(e => toast('⚠ ' + (e.message || e))); };
  $('lk').onclick = () => { if (!S.cfg.pin) { toast('عيّن رمز قفل أولاً'); return; } cl(); gate(); };
  $('ex').onclick = () => NX.saveShare('nexus-backup.json', JSON.stringify({ S: { ...S, cfg: { ...S.cfg, key: '', llm7: '', keys: {} } }, fs, mem, todo })).catch(e => toast('⚠ ' + (e.message || e)));
  $('im').onchange = async e => { try { const d = JSON.parse(await e.target.files[0].text()); S = { ...S, ...d.S, cfg: { ...S.cfg, ...d.S.cfg, key: S.cfg.key, llm7: S.cfg.llm7, keys: S.cfg.keys } }; fs = d.fs || {}; mem = d.mem || {}; todo = d.todo || []; await idb('put', 's', { S, fs, mem, todo }); location.reload(); } catch (x) { toast('ملف غير صالح'); } };
  $('lgb').onclick = unlock; $('lgp').onkeydown = e => e.key == 'Enter' && unlock();
  addEventListener('online', setStatus); addEventListener('offline', setStatus);
  // زر الرجوع في أندرويد: أغلق نافذة ← ارجع للمحادثة ← صغّر التطبيق
  NX.onBack(() => { if (dlgOpen) { $('md')._cancel?.(); return; } if (anyPanel()) { cl(); return; } if (!$('v-chat').classList.contains('on')) { show('chat'); return; } NX.minimize(); });
}

// ---------- بدء التشغيل ----------
(async () => {
  const d = await idb('get', 's');
  if (d && d.S) { S = { ...S, ...d.S, cfg: { ...DEFAULT_CFG, ...(d.S.cfg || {}) } }; fs = d.fs || {}; mem = d.mem || {}; todo = d.todo || []; }
  // ترحيل إعدادات الإصدارات القديمة
  if (['free', 'github'].includes(S.cfg.prv)) S.cfg.prv = 'auto';
  if (!S.cfg.base) S.cfg.base = DEFAULT_CFG.base;
  if (!S.sessions.length || !cur()) newS(true);
  document.body.dataset.t = S.cfg.theme || 'dark';
  bind(); setStatus(); rC(); gate();
  $('pin').textContent = S.cfg.pin ? '🔓 إزالة رمز القفل' : '🔒 تعيين رمز قفل للتطبيق';
  // تحميل الإضافة مسبقاً لتسريع أول رد
  Dev.init();
  if (S.cfg.prv == 'auto' && navigator.onLine) llm7Models().catch(() => {});
})();
