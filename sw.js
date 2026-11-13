// Service Worker for 池帥の亦殿
// 策略：页面 / version.json → 直连网络（禁缓存）；静态资源 → cache-first
// ⚠️ CACHE_NAME 由 build_posts.py 在每次发布时自动改写为 blog-v3-<build>，
//    版本变化即让浏览器认为 SW 已更新 → skipWaiting + 清理旧缓存，避免用户长期看到旧首页。
const CACHE_NAME = 'blog-v3-20261113-167-166';

const STATIC_ASSETS = [
  '/404.html',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS.map(u => new Request(u, { cache: 'reload' })));
    }).catch(err => console.log('SW install cache error:', err))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)));
    await self.clients.claim();

    // 补强：旧版本页面（无 blog-build meta，自身不会自检）在 SW 更新后
    // 直接把已打开的窗口导航到新 build，避免用户长期停留在昨天的首页。
    const build = CACHE_NAME.replace('blog-v3-', '');
    try {
      const clients = await self.clients.matchAll({ type: 'window' });
      for (const client of clients) {
        try {
          const u = new URL(client.url);
          if (u.searchParams.get('_v') === build) continue;
          u.searchParams.set('_v', build);
          await client.navigate(u.toString());
        } catch (e) { /* 单个窗口失败不影响其它 */ }
      }
    } catch (e) {}
  })());
});

self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== 'GET' && req.method !== 'HEAD') return;

  // ⚡ 详情页引用的境外渲染阻塞资源（Google Fonts / cdnjs 代码高亮）在国内经常超时，
  //    同步 <script> 和 <link rel=stylesheet> 会一直卡住首屏。1.5 秒内拿不到就返回
  //    同类型的空资源：高亮 JS 给一个 stub（详情页自身是 typeof hljs 判断，不会报错），
  //    CSS 给空样式（字体回退到系统字）。网络正常时仍加载真实资源，样式不变。
  const host = url.hostname;
  if (host === 'fonts.googleapis.com' || host === 'fonts.gstatic.com' || host === 'cdnjs.cloudflare.com') {
    const isJs = /\.js(\?|$)/.test(url.pathname);
    const empty = () => new Response(
      isJs ? 'window.hljs=window.hljs||{highlightAll:function(){},highlightElement:function(){}};' : '',
      { status: 200, headers: { 'Content-Type': isJs ? 'application/javascript; charset=utf-8' : 'text/css; charset=utf-8' } }
    );
    event.respondWith(new Promise(resolve => {
      let done = false;
      const t = setTimeout(() => { if (!done) { done = true; resolve(empty()); } }, 1500);
      fetch(req).then(r => {
        if (!done) { done = true; clearTimeout(t); resolve(r); }
      }).catch(() => {
        if (!done) { done = true; clearTimeout(t); resolve(empty()); }
      });
    }));
    return;
  }

  if (url.hostname !== 'cdyrh.github.io' && url.hostname !== 'www.aj1j.com') return;
  if (url.pathname.startsWith('/admin')) return;

  // ⚠️ HEAD 探测不拦截：旧版把它走了 cache-first，导致首页版本检测拿到永久不变的响应，
  //    博客从此不再自动刷新。这里直接放行给网络。
  if (req.method === 'HEAD') return;

  // 版本号文件与 SW 自身：永不缓存，保证发布后能被立刻感知
  if (url.pathname === '/version.json' || url.pathname === '/sw.js'
      || url.pathname === '/hot_tags.json') return;

  const accept = req.headers.get('accept') || '';
  const isPage = accept.includes('text/html')
    || url.pathname === '/'
    || url.pathname.endsWith('.html')
    || url.pathname.endsWith('.xml');

  // ⚡ 页面与 RSS：stale-while-revalidate（缓存优先，后台静默更新）
  // 以前是 network-first + no-store，每次打开都要等 GitHub Pages 回源，国内往往几秒起步。
  // 现在同一 build 内重复打开直接读缓存（毫秒级），后台再拉取新版写回缓存。
  // 缓存 key 带 CACHE_NAME：build_posts.py 每次发文都会改写 CACHE_NAME，
  // 新版本自动 miss → 走网络拿最新 HTML，不会出现「一直看旧文章」。
  // 另有 version.json 轮询 + ?_v= 强制重载作为第二重保险。
  if (isPage) {
    const pageKey = url.pathname + '?__sw=' + CACHE_NAME;
    const network = fetch(req, { cache: 'no-store' }).then(response => {
      if (response && response.ok) {
        const cloned = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(pageKey, cloned)).catch(() => {});
      }
      return response;
    }).catch(() => null);

    event.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        const cached = await cache.match(pageKey);
        if (cached) {
          event.waitUntil(network);   // 后台刷新，不阻塞本次渲染
          return cached;
        }
        const fresh = await network;
        if (fresh) return fresh;
        const fallback = await cache.match(req);
        return fallback || caches.match('/404.html') || Response.error();
      })
    );
    return;
  }

  // 静态资源：cache-first
  event.respondWith(
    caches.match(req).then(cached => {
      return cached || fetch(req).then(response => {
        if (response && response.ok) {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, cloned)).catch(() => {});
        }
        return response;
      });
    })
  );
});
