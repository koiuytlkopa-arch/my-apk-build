// Nexus Pro: محرك إجابات خاص بنا — بلا نموذج لغوي خارجي ولا مفاتيح.
// يبحث على الإنترنت، يقرأ أفضل الصفحات، ثم يختار الجمل الأكثر صلة بالسؤال ويعرضها مع المصادر.
const PRO_STOP = new Set(['من', 'في', 'على', 'الى', 'إلى', 'عن', 'و', 'او', 'أو', 'ما', 'ماذا', 'هو', 'هي', 'هل', 'كيف', 'the', 'a', 'an', 'of', 'is', 'and', 'to', 'in', 'what', 'how']);
const proNorm = s => s.toLowerCase().replace(/[ً-ْ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي');
const proTerms = s => proNorm(s).split(/[^\p{L}\p{N}]+/u).filter(w => w.length > 1 && !PRO_STOP.has(w));
const proSentences = t => t.split(/(?<=[.!?؟])\s+|\n+/).map(s => s.trim()).filter(s => s.length > 25 && s.length < 400);
// ترتيب الجمل: عدد الكلمات المشتركة مع السؤال، مع تفضيل الجمل المركّزة (غير الطويلة جداً)
function proRank(q, docs) {
  const qt = [...new Set(proTerms(q))], out = [], seen = new Set();
  for (const d of docs) for (const s of proSentences(d.text)) {
    if (seen.has(s)) continue; seen.add(s);
    const st = new Set(proTerms(s)); let hit = 0;
    for (const w of qt) if (st.has(w)) hit++;
    if (hit) out.push({ s, url: d.url, sc: hit / Math.sqrt(st.size + 2) + hit * 0.25 });
  }
  return out.sort((a, b) => b.sc - a.sc);
}
async function proAnswer(q) {
  const s = await smartSearch(q), docs = [];
  for (const x of s.results.slice(0, 3)) {
    try { const r = await net(x.url); docs.push({ url: x.url, text: strip(r.text).slice(0, 30000) }); }
    catch (e) { if (e.name == 'AbortError') throw e; }
  }
  if (!docs.length) docs.push(...s.results.map(x => ({ url: x.url, text: x.title + '. ' + (x.snippet || '') })));
  const top = proRank(q, docs).slice(0, 4);
  if (!top.length) return 'لم أجد إجابة واضحة في المصادر المتاحة. جرّب صياغة أدق للسؤال.';
  const srcs = [...new Set(top.map(t => t.url))];
  return top.map(t => t.s).join(' ') + '\n\nالمصادر:\n' + srcs.map(u => '- ' + u).join('\n');
}
