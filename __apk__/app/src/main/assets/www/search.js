// Nexus Search v9: بحث متعدد المصادر (Tavily ← Brave ← DuckDuckGo ← Wikipedia) + بحث معمّق
async function smartSearch(q) {
  const K = S.cfg.keys || {};
  if (K.tavily) {
    try {
      const r = await net('https://api.tavily.com/search', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + K.tavily }, body: JSON.stringify({ query: q, max_results: 6, include_answer: true }) });
      const j = JSON.parse(r.text);
      if (j.results && j.results.length) return { source: 'tavily', answer: j.answer || '', results: j.results.map(x => ({ title: x.title, url: x.url, snippet: String(x.content || '').slice(0, 300) })) };
    } catch (e) { if (e.name == 'AbortError') throw e; }
  }
  if (K.brave) {
    try {
      const r = await net('https://api.search.brave.com/res/v1/web/search?q=' + encodeURIComponent(q) + '&count=6', { method: 'GET', headers: { 'X-Subscription-Token': K.brave, Accept: 'application/json' } });
      const x = JSON.parse(r.text).web?.results || [];
      if (x.length) return { source: 'brave', results: x.map(y => ({ title: y.title, url: y.url, snippet: strip(y.description || '').slice(0, 300) })) };
    } catch (e) { if (e.name == 'AbortError') throw e; }
  }
  let r = []; try { r = await ddgSearch(q); } catch (e) { if (e.name == 'AbortError') throw e; }
  if (r.length) return { source: 'duckduckgo', results: r };
  return { source: 'wikipedia', results: await wikiSearch(q) };
}
// بحث معمّق: يبحث ثم يقرأ أفضل 3 صفحات
T.research = ['query', 'بحث معمّق: يبحث ثم يجلب نص أفضل 3 صفحات للمقارنة والتلخيص مع الروابط', async a => {
  const s = await smartSearch(a.query), pages = [];
  for (const x of s.results.slice(0, 3)) {
    try { const r = await net(x.url); pages.push({ url: x.url, text: strip(r.text).slice(0, 2300) }); } catch (e) { if (e.name == 'AbortError') throw e; }
  }
  return { note: UNTRUSTED, answer: s.answer || '', sources: s.results.map(x => x.url), pages };
}];
SENS.add('research');
