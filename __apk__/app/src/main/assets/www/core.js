// النواة: الحالة، التخزين، الحوارات، أدوات مساعدة
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const AF = Object.getPrototypeOf(async function () {}).constructor;
const isHtml = p => /\.html?$/i.test(p);
const isBin = v => typeof v === 'string' && v.startsWith('data:');

const DEFAULT_CFG = { prv: 'auto', model: '', base: 'https://api.llm7.io/v1', key: '', llm7: '', auto: 'safe', role: 'general', theme: 'dark', pin: null, lastModel: '', keys: {}, learn: 'on' };
let S = { cfg: { ...DEFAULT_CFG }, sessions: [], cur: null, audit: [] };
let fs = {}, mem = {}, todo = [], busy = false, stop = false, ctl = new AbortController();
let allowAll = false; // "سماح دائماً" لهذه الجلسة فقط (لا يُحفظ)

const cur = () => S.sessions.find(x => x.id == S.cur);
const H = () => cur().hist;

// ---------- تخزين دائم (IndexedDB) ----------
const dbp = new Promise(r => {
  try {
    const q = indexedDB.open('nexus', 1);
    q.onupgradeneeded = () => q.result.createObjectStore('k');
    q.onsuccess = () => r(q.result);
    q.onerror = () => r(null);
  } catch (e) { r(null); }
});
const idb = async (m, k, v) => {
  const d = await dbp; if (!d) return undefined;
  return new Promise(r => {
    try {
      const s = d.transaction('k', m == 'get' ? 'readonly' : 'readwrite').objectStore('k'), q = m == 'get' ? s.get(k) : s.put(v, k);
      q.onsuccess = () => r(q.result); q.onerror = () => r(undefined);
    } catch (e) { r(undefined); }
  });
};
let saveT;
const sv = () => { clearTimeout(saveT); saveT = setTimeout(() => idb('put', 's', { S, fs, mem, todo }), 300); };

// ---------- واجهة: توست وحوارات ----------
function toast(msg, ms = 2600) {
  const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg;
  $('toasts').appendChild(t); setTimeout(() => t.classList.add('out'), ms - 300); setTimeout(() => t.remove(), ms);
}
// dialog({title, body, input, buttons:[{id,label,cls}]}) → Promise<{id,value}>
let dlgOpen = false;
function dialog({ title, body = '', input = null, buttons }) {
  return new Promise(res => {
    const m = $('md'); dlgOpen = true;
    m.innerHTML = `<div class="box"><h3>${esc(title)}</h3><div class="bd">${esc(body).replace(/\n/g, '<br>')}</div>${input ? `<input id="mdi" type="${input.type || 'text'}" inputmode="${input.mode || 'text'}" placeholder="${esc(input.ph || '')}" autocomplete="off">` : ''}<div class="btns"></div></div>`;
    const done = id => { m.classList.remove('on'); dlgOpen = false; res({ id, value: input ? $('mdi').value : '' }); };
    buttons.forEach(b => { const e = document.createElement('button'); e.textContent = b.label; e.className = b.cls || ''; e.onclick = () => done(b.id); m.querySelector('.btns').appendChild(e); });
    m.onclick = e => { if (e.target === m) done('cancel'); };
    m.classList.add('on'); if (input) setTimeout(() => $('mdi').focus(), 50);
    m._cancel = () => done('cancel');
  });
}
const confirmD = async (title, body, ok = 'موافق') => (await dialog({ title, body, buttons: [{ id: 'cancel', label: 'إلغاء' }, { id: 'ok', label: ok, cls: 'go' }] })).id == 'ok';
const promptD = async (title, body = '', ph = '', type = 'text', mode = 'text') => { const r = await dialog({ title, body, input: { ph, type, mode }, buttons: [{ id: 'cancel', label: 'إلغاء' }, { id: 'ok', label: 'تم', cls: 'go' }] }); return r.id == 'ok' ? r.value : null; };

// ---------- ملفات ثنائية و ZIP ----------
const u2a = u => { const b = atob(u.split(',')[1]), a = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a; };
const b2u = b => new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(b); });
const crcT = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc = b => { let c = -1; for (const x of b) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ -1) >>> 0; };
function zip(files) {
  const E = new TextEncoder(), parts = [], cd = [], n = Object.keys(files).length; let off = 0, cs = 0;
  for (const [k, d] of Object.entries(files)) {
    const nb = E.encode(k), db = typeof d == 'string' ? (d.startsWith('data:') ? u2a(d) : E.encode(d)) : d, c = crc(db);
    const h = new DataView(new ArrayBuffer(30)); h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint32(14, c, true); h.setUint32(18, db.length, true); h.setUint32(22, db.length, true); h.setUint16(26, nb.length, true); parts.push(h.buffer, nb, db);
    const e = new DataView(new ArrayBuffer(46)); e.setUint32(0, 0x02014b50, true); e.setUint16(4, 20, true); e.setUint16(6, 20, true); e.setUint16(8, 0x0800, true); e.setUint32(16, c, true); e.setUint32(20, db.length, true); e.setUint32(24, db.length, true); e.setUint16(28, nb.length, true); e.setUint32(42, off, true); cd.push(e.buffer, nb); off += 30 + nb.length + db.length; cs += 46 + nb.length;
  }
  const r = new DataView(new ArrayBuffer(22)); r.setUint32(0, 0x06054b50, true); r.setUint16(8, n, true); r.setUint16(10, n, true); r.setUint32(12, cs, true); r.setUint32(16, off, true);
  return new Blob([...parts, ...cd, r.buffer], { type: 'application/zip' });
}

// ---------- شبكة ----------
const strip = h => h.replace(/<(script|style)[\s\S]*?<\/\1>/gi, '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
// طلب مع مهلة وإمكانية الإيقاف من المستخدم
async function post(u, o = {}, ms = 90000) {
  const ac = new AbortController(); let to;
  const tp = new Promise((_, j) => { to = setTimeout(() => { ac.abort(); j(new Error('⏱ انتهت المهلة: النموذج لا يرد. تأكد من الإنترنت.')); }, ms); });
  const sp = new Promise((_, j) => {
    const f = () => { ac.abort(); j(new DOMException('stopped', 'AbortError')); };
    if (ctl.signal.aborted) f(); else ctl.signal.addEventListener('abort', f, { once: true });
  });
  const run = (async () => {
    const r = await fetch(u, { ...o, signal: ac.signal }), tx = await r.text();
    let j; try { j = JSON.parse(tx); } catch (e) { j = { error: { message: tx.slice(0, 200) || 'HTTP ' + r.status } }; }
    return [r, j, tx];
  })();
  try { return await Promise.race([run, tp, sp]); } finally { clearTimeout(to); run.catch(() => {}); }
}
const NC = {};
const net = async (u, o) => {
  if (!o && NC[u] && Date.now() - NC[u].t < 3e5) return NC[u].v;
  const [r, , tx] = await post(u, o || {}, 25000), v = { status: r.status, text: tx };
  if (!o) NC[u] = { t: Date.now(), v };
  return v;
};

// ---------- قوالب الرسم ----------
const TPL = {
  animation: "ctx.fillStyle='#0b1020';ctx.fillRect(0,0,w,h);for(let i=0;i<40;i++){const a=t+i*.3,r=80+i*8;ctx.fillStyle=`hsl(${i*9+t*60},90%,60%)`;ctx.beginPath();ctx.arc(w/2+Math.cos(a)*r,h/2+Math.sin(a*1.3)*r,6+i/4,0,7);ctx.fill()}",
  story: "const S=['الجملة الأولى','الجملة الثانية','الجملة الثالثة'],d=2,i=Math.min(S.length-1,t/d|0),k=t/d%1,al=Math.min(1,k*3,(1-k)*3+.2);ctx.fillStyle='#0b1020';ctx.fillRect(0,0,w,h);ctx.globalAlpha=al;ctx.fillStyle='#fff';ctx.font='bold 56px sans-serif';ctx.textAlign='center';ctx.fillText(S[i],w/2,h/2);ctx.globalAlpha=1",
  chart: "const D=[30,70,45,90,60],m=Math.max(...D);ctx.fillStyle='#0b1020';ctx.fillRect(0,0,w,h);D.forEach((v,i)=>{const bh=v/m*h*.6*Math.min(1,t);ctx.fillStyle=`hsl(${i*50+200},80%,60%)`;ctx.fillRect(w*.1+i*w*.17,h*.8-bh,w*.12,bh)})"
};

// ---------- مشروع APK المُولَّد من داخل التطبيق ----------
const WF = `name: Build APK
on:
  push:
    branches: [main, master]
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 17
      - run: npm install
      - run: npx cap add android
      - run: npx cap sync android
      - run: cd android && chmod +x gradlew && ./gradlew assembleDebug --no-daemon
      - run: cp android/app/build/outputs/apk/debug/app-debug.apk App.apk
      - uses: actions/upload-artifact@v4
        with:
          name: APK
          path: App.apk
`;
