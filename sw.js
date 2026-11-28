// Service Worker for 池帥の亦殿
// 策略：页面 / version.json → 直连网络（禁缓存）；静态资源 → cache-first
// ⚠️ CACHE_NAME 由 build_posts.py 在每次发布时自动改写为 blog-v3-<build>，
//    版本变化即让浏览器认为 SW 已更新 → skipWaiting + 清理旧缓存，避免用户长期看到旧首页。
const CACHE_NAME = 'blog-v3-20261128-182-181';

const STATIC_ASSETS = [
  '/404.html',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    // ⚡ 每次 sw.js 本身发生变化（哪怕 CACHE_NAME 没变，例如只改了取数策略），
    //    都把全部旧缓存清掉再重建。否则同一 build 内留下的旧首页 HTML 会在
    //    网络超时时被当作兜底返回，用户又会看到旧日期首页。
    //    注意：CACHE_NAME 未变时浏览器不会重复 install，所以这里只在 SW 真更新时执行一次。
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map(k => caches.delete(k)));
    } catch (e) { /* 清缓存失败不影响安装 */ }
    try {
      const cache = await caches.open(CACHE_NAME);
      await cache.addAll(STATIC_ASSETS.map(u => new Request(u, { cache: 'reload' })));
    } catch (err) {
      console.log('SW install cache error:', err);
    }
  })());
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

  // ⚡ 页面与 RSS：network-first（最多等 4 秒，超时降级缓存）
  //
  // 【为什么不再用 stale-while-revalidate】旧版是「缓存优先 + 后台更新」，虽然快，
  // 但用户在发布次日打开首页时，SW 直接把上一份缓存 HTML 吐出来（stale），
  // 而缓存 key 只取 pathname、不含 query —— 所以前端自检 reload 到 ?_v=<build>
  // 依然命中同一份旧缓存，等于白重载，必须手动再刷一次才更新。
  // 这正是「打开还是昨天首页、手动刷新才出最新」的根因。
  //
  // 改为 network-first 后：每次打开都先向服务器要最新 HTML，拿到就渲染并回写缓存；
  // 网络慢/断网时最多等 4 秒后回落到缓存，不会白屏；后台仍会把成功响应写入缓存。
  // 对自检触发的强制重载（URL 带 _v=）放宽到 9 秒，避免刚 reload 又回落旧缓存。
  if (isPage) {
    const pageKey = url.pathname + '?__sw=' + CACHE_NAME;
    const isForcedReload = url.searchParams.has('_v');
    const TIMEOUT = isForcedReload ? 9000 : 4000;

    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const network = fetch(req, { cache: 'no-store' }).then(response => {
        if (response && response.ok) {
          cache.put(pageKey, response.clone()).catch(() => {});
        }
        return response;
      });
      network.catch(() => {});   // 超时后 network 仍会跑完，先吞掉可能的未处理拒绝

      const cached = await cache.match(pageKey);

      // 首次访问（无任何缓存）：只能等网络
      if (!cached) {
        try {
          return await network;
        } catch (e) {
          return (await caches.match('/404.html')) || Response.error();
        }
      }

      // 有缓存兜底：优先网络，超时才用缓存
      try {
        return await Promise.race([
          network,
          new Promise((_, reject) => setTimeout(() => reject(new Error('sw-timeout')), TIMEOUT))
        ]);
      } catch (e) {
        return cached;
      }
    })());
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
