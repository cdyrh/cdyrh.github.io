#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""warmup.py —— 发布后「预热 + 线上校验」，让新文章立刻能在页面上刷出来

为什么需要它：
    GitHub Pages 的 CDN 对 index.html 有 max-age=600 的缓存。push 完立刻访问，
    很可能仍然拿到 10 分钟前的旧页面（=用户看到的「昨天的文章」）。
    本脚本用「带唯一 query 的 URL」请求线上，强制 CDN 回源并缓存最新版，
    用户端 index.html 的自动检测逻辑随后用同样的 ?_v=<build> URL 重载，一定拿到新页面。

用法：
    python warmup.py                 # 用本地 version.json 的 build 校验
    python warmup.py --timeout 600   # 自定义最长等待秒数
    python warmup.py --quiet

退出码：
    0  线上已生效（version.json / 首页 / 详情页 全部正确）
    1  超时未生效（打印未通过的项）
"""
import json, os, re, sys, time, argparse, urllib.request, urllib.error, random

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = 'https://www.aj1j.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) warmup/1.0'


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def uniq(url):
    sep = '&' if '?' in url else '?'
    return url + sep + 't=' + str(int(time.time() * 1000)) + '-' + str(random.randint(1000, 9999))


def check_online(build, latest_id):
    """返回 (ok, items) —— items 是 [(名称, 是否通过, 说明)]"""
    items = []

    # 1) version.json 的 build 是否已更新
    ok_ver = False
    try:
        st, raw = fetch(uniq(SITE + '/version.json'))
        d = json.loads(raw.decode('utf-8'))
        ok_ver = (d.get('build') == build)
        items.append(('version.json', ok_ver, 'build=%s (期望 %s)' % (d.get('build'), build)))
    except Exception as e:
        items.append(('version.json', False, '请求失败: %s' % e))

    # 2) 首页 ?_v=<build>：强制 CDN 回源，并校验 posts-data 首篇
    ok_home = False
    note = ''
    try:
        st, raw = fetch(SITE + '/index.html?_v=' + build)
        html = raw.decode('utf-8', 'replace')
        m = re.search(r'<script type="application/json" id="posts-data">(.*?)</script>', html, re.S)
        if not m:
            note = 'posts-data 块缺失'
        else:
            posts = json.loads(m.group(1).replace('\\u003c', '<'))
            top = sorted([p for p in posts if p.get('top')], key=lambda p: (-int(p.get('pin') or 0), -(p.get('id') or 0)))
            first = (top or sorted(posts, key=lambda p: -(p.get('id') or 0)))[0]
            ok_home = (first.get('id') == latest_id)
            note = '首页首位 id=%s 日期=%s（期望 id=%s）' % (first.get('id'), first.get('date'), latest_id)
        m2 = re.search(r'<meta name="blog-build" content="([^"]+)">', html)
        items.append(('首页 posts-data', ok_home, note))
        items.append(('首页 blog-build meta', bool(m2) and m2.group(1) == build,
                      (m2.group(1) if m2 else '缺失')))
    except Exception as e:
        items.append(('首页 posts-data', False, '请求失败: %s' % e))

    # 3) 详情页可用性与关键元素
    ok_post = False
    try:
        st, raw = fetch(uniq('%s/blog_posts/post_%s.html' % (SITE, latest_id)))
        ph = raw.decode('utf-8', 'replace')
        need = ['share-bar"', 'comment-section', 'back-home"', 'id="post-body"']
        missing = [k for k in need if k not in ph]
        ok_post = (st == 200 and not missing)
        items.append(('详情页 post_%s.html' % latest_id, ok_post,
                      'HTTP %s' % st + ('' if not missing else '，缺少: %s' % ','.join(missing))))
    except Exception as e:
        items.append(('详情页 post_%s.html' % latest_id, False, '请求失败: %s' % e))

    # 4) sw.js 缓存版本
    try:
        st, raw = fetch(uniq(SITE + '/sw.js'))
        swt = raw.decode('utf-8', 'replace')
        m = re.search(r"const CACHE_NAME = '([^']+)';", swt)
        items.append(('sw.js 缓存版本', bool(m) and build in m.group(1),
                      (m.group(1) if m else '缺失')))
    except Exception as e:
        items.append(('sw.js 缓存版本', False, '请求失败: %s' % e))

    return all(i[1] for i in items), items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=int, default=600, help='最长等待秒数，默认 600')
    ap.add_argument('--interval', type=int, default=20, help='轮询间隔秒数，默认 20')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    ver = json.load(open(os.path.join(HERE, 'version.json'), encoding='utf-8'))
    build, latest_id = ver['build'], ver['latestId']
    if not args.quiet:
        print('本地 build=%s  latestId=%s  《%s》' % (build, latest_id, ver.get('latestTitle', '')))

    deadline = time.time() + args.timeout
    attempt = 0
    while True:
        attempt += 1
        ok, items = check_online(build, latest_id)
        if not args.quiet:
            print('--- 第 %d 轮（已等 %ds）---' % (attempt, args.timeout - int(deadline - time.time())))
            for name, passed, note in items:
                print('  %s %s：%s' % ('✅' if passed else '⏳', name, note))
        if ok:
            print('🎉 线上已生效：首页首位已是 id=%s，页面 60 秒内会自动刷新到最新。' % latest_id)
            return 0
        if time.time() + args.interval > deadline:
            print('⚠️ 超时：%ds 内线上仍未生效，请检查 GitHub Pages 部署状态或手动重跑。' % args.timeout)
            return 1
        time.sleep(args.interval)


if __name__ == '__main__':
    sys.exit(main())
