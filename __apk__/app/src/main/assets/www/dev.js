// Nexus Device v8: نموذج على الجهاز (LiteRT-LM عبر إضافة NexusLLM) — يعمل بلا إنترنت
const PLG = () => (window.Capacitor && Capacitor.isNativePlatform && Capacitor.isNativePlatform() ? Capacitor.registerPlugin('NexusLLM') : null);
const GEMMA3N = 'https://huggingface.co/google/gemma-3n-E2B-it-litert-lm/resolve/main/gemma-3n-E2B-it-int4.litertlm';
const DEV_SYS = () => `أنت Nexus وكيل يعمل على الجهاز. أجب بلغة المستخدم وباختصار. لتنفيذ شيء اكتب سطراً واحداً: <tool>{"name":"الأداة","args":{...}}</tool> ثم توقف وانتظر <result>. لا تخترع النتائج.
الأدوات: write_file(path,content) read_file(path) edit_file(path,find,replace) list_files() preview_html(path) run_js(code) web_search(query) fetch_url(url) calc(expr) remember(key,value) todo_set(items)
للمشاريع المرئية: اكتب ملف HTML واحداً ثم preview_html.
${Brain.lessons()}`;
const Dev = {
  ready: false, p: null,
  async init() {
    const p = PLG(); if (!p) return;
    try { await p.status(); Dev.p = p; if (S.cfg.devModel) { await p.load({ name: S.cfg.devModel }); Dev.ready = true; } } catch (e) { /* الإضافة غير موجودة في هذه النسخة */ }
    setStatus();
  },
  ui() {
    if (!$('dv-url').value) $('dv-url').value = GEMMA3N;
    $('dv-st').textContent = !Dev.p ? 'غير متاح في هذه النسخة — ابنِ workflow «Build APK (on-device model)»' : Dev.ready ? '✅ يعمل على الجهاز: ' + S.cfg.devModel : 'الإضافة جاهزة — نزّل نموذجاً';
  },
  async install() {
    const p = Dev.p; if (!p) return toast('يلزم APK الخاص بالنموذج المحلي');
    const url = $('dv-url').value.trim(), tok = $('dv-tok').value.trim(), name = url.split('/').pop().split('?')[0] || 'model.litertlm';
    try {
      const h = await p.addListener('progress', e => { $('dv-st').textContent = '⬇ ' + (e.total > 0 ? Math.round(e.done / e.total * 100) + '%' : Math.round(e.done / 1048576) + ' MB'); });
      try { await p.download({ url, name, token: tok }); } finally { h.remove(); }
      $('dv-st').textContent = '⏳ جاري تحميل النموذج في الذاكرة…';
      await p.load({ name }); S.cfg.devModel = name; Dev.ready = true; sv(); setStatus(); Dev.ui(); toast('النموذج المحلي جاهز');
    } catch (e) { $('dv-st').textContent = '⚠ ' + (e.message || e); }
  },
  // مدخل مضغوط: السياق صغير على الأجهزة، فنرسل تعليمات مختصرة + آخر المحادثة فقط
  async chat(msgs) {
    if (!Dev.ready) throw new Error('النموذج المحلي غير جاهز');
    let tx = ''; const h = msgs.slice(1);
    for (let i = h.length - 1; i >= 0; i--) { const s = (h[i].role == 'user' ? 'المستخدم: ' : 'المساعد: ') + h[i].content + '\n'; if (tx.length + s.length > 6000) break; tx = s + tx; }
    const r = await Dev.p.generate({ prompt: DEV_SYS() + '\n\n' + tx + 'المساعد:' });
    if (!r.text || !r.text.trim()) throw new Error('رد فارغ من النموذج المحلي');
    return clean(r.text);
  }
};
