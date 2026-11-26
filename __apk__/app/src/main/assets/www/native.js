// جسر الميزات الأصلية (Capacitor) مع بدائل للمتصفح — يعمل داخل الـAPK وخارجه
(() => {
  const C = window.Capacitor;
  const P = () => (C && C.Plugins) || {};
  const native = !!(C && C.isNativePlatform && C.isNativePlatform());
  const MIME = { html: 'text/html', htm: 'text/html', json: 'application/json', md: 'text/markdown', txt: 'text/plain', csv: 'text/csv', js: 'text/javascript', css: 'text/css', svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', zip: 'application/zip', mp4: 'video/mp4', webm: 'video/webm' };
  const ext = n => (n.split('.').pop() || '').toLowerCase();

  const bytesOf = data => {
    if (typeof data === 'string' && data.startsWith('data:')) {
      const b = atob(data.split(',')[1]), a = new Uint8Array(b.length);
      for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);
      return a;
    }
    return new TextEncoder().encode(String(data));
  };
  const b64 = u8 => {
    let s = '';
    for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return btoa(s);
  };
  const mimeOf = (name, data) => (typeof data === 'string' && data.startsWith('data:') ? data.match(/:(.*?);/)[1] : MIME[ext(name)] || 'application/octet-stream');
  const cancelled = e => /cancel/i.test(String((e && e.message) || e));

  window.NX = {
    native,
    // حفظ/مشاركة ملف: على أندرويد يُكتب في الكاش ثم تُفتح قائمة المشاركة (حفظ في الملفات، واتساب، درايف...)
    async saveShare(name, data) {
      const u8 = bytesOf(data), mime = mimeOf(name, data);
      const fsP = P().Filesystem, shP = P().Share;
      if (native && fsP && shP) {
        const safe = name.replace(/[^\w.\-؀-ۿ]+/g, '_');
        const w = await fsP.writeFile({ path: 'nexus/' + safe, data: b64(u8), directory: 'CACHE', recursive: true });
        try { await shP.share({ title: safe, dialogTitle: 'حفظ أو مشاركة: ' + safe, files: [w.uri] }); } catch (e) { if (!cancelled(e)) throw e; }
        return 'shared';
      }
      const file = new File([u8], name.split('/').pop(), { type: mime });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        try { await navigator.share({ files: [file] }); return 'shared'; } catch (e) { if (!cancelled(e) && e.name !== 'AbortError') throw e; return 'shared'; }
      }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(file); a.download = file.name; document.body.appendChild(a); a.click(); a.remove();
      return 'downloaded';
    },
    async shareText(text) {
      if (native && P().Share) { try { await P().Share.share({ text }); } catch (e) { if (!cancelled(e)) throw e; } return 'ok'; }
      if (navigator.share) { await navigator.share({ text }); return 'ok'; }
      await this.copy(text); return 'copied';
    },
    async copy(text) {
      if (native && P().Clipboard) { await P().Clipboard.write({ string: text }); return; }
      await navigator.clipboard.writeText(text);
    },
    async paste() {
      if (native && P().Clipboard) { const r = await P().Clipboard.read(); return r.value || ''; }
      return navigator.clipboard.readText();
    },
    async notify(title, body) {
      const ln = P().LocalNotifications;
      if (native && ln) {
        const p = await ln.requestPermissions();
        if (p.display !== 'granted') throw 'المستخدم لم يمنح إذن الإشعارات';
        await ln.schedule({ notifications: [{ id: Date.now() % 2147483000, title, body, schedule: { at: new Date(Date.now() + 400) } }] });
        return 'ok';
      }
      if (!('Notification' in window)) throw 'الإشعارات غير مدعومة';
      if ((await Notification.requestPermission()) !== 'granted') throw 'تم رفض الإذن';
      new Notification(title, { body }); return 'ok';
    },
    async location() {
      const g = P().Geolocation;
      if (native && g) {
        const p = await g.requestPermissions();
        if (p.location !== 'granted' && p.coarseLocation !== 'granted') throw 'تم رفض إذن الموقع';
        const r = await g.getCurrentPosition({ enableHighAccuracy: true, timeout: 15000 });
        return { lat: r.coords.latitude, lng: r.coords.longitude, accuracy: r.coords.accuracy };
      }
      return new Promise((s, j) => navigator.geolocation.getCurrentPosition(p => s({ lat: p.coords.latitude, lng: p.coords.longitude }), e => j(e.message)));
    },
    async vibrate(ms) {
      const h = P().Haptics;
      if (native && h) { await h.vibrate({ duration: ms || 200 }); return 'ok'; }
      if (navigator.vibrate) { navigator.vibrate(ms || 200); return 'ok'; }
      throw 'الاهتزاز غير مدعوم';
    },
    async battery() {
      try { if (navigator.getBattery) { const b = await navigator.getBattery(); return { level: b.level, charging: b.charging }; } } catch (e) { /* ignore */ }
      return null;
    },
    onBack(fn) {
      try { const a = P().App; if (native && a && a.addListener) a.addListener('backButton', fn); } catch (e) { /* ignore */ }
    },
    minimize() { try { P().App.minimizeApp(); } catch (e) { /* ignore */ } }
  };
})();
