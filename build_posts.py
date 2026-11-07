#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_posts.py —— 博客数据源「可复现」生成器（永久修复配套）

为什么需要它：
    旧机制把 57 篇文章正文以 JS 模板字符串内联进 index.html 的 DB.posts = [...]。
    一旦某篇正文含未转义的反引号/`${`，整个 <script> 解析失败 → 首页白屏。
    而且线上文件里数组收尾的 `]` 还丢失了，属于结构性损坏。

新机制（永久修复）：
    文章数据单一来源 = posts_data.json（标准 JSON，绝不会被正文反引号破坏）。
    index.html 通过 <script id="posts-data"> 安全嵌入，运行时 JSON.parse + try/catch 容错。
    本脚本负责把 posts_data.json「编译」成：
      1) index.html 里的 posts-data JSON 块（覆盖式更新）
      2) feed.xml（RSS 2.0，正文用站点同款 md2html 渲染）

每日发文章的正确姿势（见自动化）：
    把新文章追加进 posts_data.json（干净 JSON），然后跑本脚本，再 git push。
    绝不要再手写/拼接 DB.posts 模板字符串。

依赖：Node（用于调用站点 md2html 渲染正文）。
"""
import re, json, subprocess, os, datetime, sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
DATA = os.path.join(HERE, 'posts_data.json')
FEED = os.path.join(HERE, 'feed.xml')
VERSION = os.path.join(HERE, 'version.json')
SW = os.path.join(HERE, 'sw.js')
NODE = r'C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2\node.exe'

SITE = 'https://cdyrh.github.io/'


def load_posts():
    posts = json.load(open(DATA, encoding='utf-8'))
    # 按 id 降序（最新在前），与历史展示顺序一致
    posts.sort(key=lambda p: p.get('id', 0), reverse=True)
    return posts


def extract_md2html(html):
    i = html.find('function md2html')
    if i < 0:
        raise RuntimeError('index.html 中找不到 function md2html')
    depth = 0
    started = False
    j = i
    while j < len(html):
        c = html[j]
        if c == '{':
            depth += 1
            started = True
        elif c == '}':
            depth -= 1
            if started and depth == 0:
                break
        j += 1
    return html[i:j + 1]


def plain_text(md):
    """把 Markdown 正文压成纯文本（口径与前端 getExcerpt 一致，另外剥掉图片/链接）。"""
    s = re.sub(r'```[\s\S]*?```', '', md or '')
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', s)          # 图片
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)       # 链接文字保留
    s = re.sub(r'https?://\S+', '', s)
    s = re.sub(r'[#*`>_!|\[\]]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def word_count(md):
    """与前端 countWords 同口径：中文按字、英文按词。"""
    s = re.sub(r'```[\s\S]*?```', '', md or '')
    s = re.sub(r'[#*`>_\[\]!]', '', s)
    s = re.sub(r'https?://\S+', '', s).strip()
    return len(re.findall(r'[\u4e00-\u9fa5]', s)) + len(re.findall(r'[a-zA-Z]+', s))


# 首页列表需要的字段（body 全文不进首页，点文章会跳到独立静态页）
SLIM_FIELDS = ('id', 'title', 'cat', 'tags', 'cover', 'date', 'views',
               'top', 'draft', 'pin', 'thumb', 'private', 'summary', 'excerpt')


def slim_post(p):
    """首页瘦身数据：元数据 + 摘要 + 字数，去掉 body 全文。"""
    out = {k: p[k] for k in SLIM_FIELDS if k in p}
    out['excerpt'] = plain_text(p.get('body', ''))[:240]
    out['words'] = word_count(p.get('body', ''))
    return out


def update_index_block(posts):
    # ⚡ 首页只注入列表数据。以前把 160 篇全文一起塞进 HTML，首页高达 978KB，
    #    国内访问 GitHub Pages 要等几秒甚至几十秒，左侧列表必须等整个 HTML 下完才渲染。
    #    正文由 build_feed / 独立静态详情页承载，首页不需要 body。
    slim = [slim_post(p) for p in posts]
    html = open(INDEX, encoding='utf-8').read()
    json_text = json.dumps(slim, ensure_ascii=False).replace('<', '\\u003c')
    new_block = '<script type="application/json" id="posts-data">\n' + json_text + '\n</script>'
    pat = re.compile(r'<script type="application/json" id="posts-data">.*?</script>', re.S)
    if pat.search(html):
        # 注意：必须用函数式替换，否则 re.sub 会把 new_block 里的反斜杠当转义，
        # 导致 JSON 的 \n 转义被解释成真实换行符 → JSON 非法。
        html = pat.sub(lambda m: new_block, html, count=1)
    else:
        s = html.rfind('<script>')
        if s < 0:
            raise RuntimeError('找不到注入位置')
        html = html[:s] + new_block + '\n' + html[s:]
    open(INDEX, 'w', encoding='utf-8').write(html)
    raw = len(json.dumps(posts, ensure_ascii=False).encode('utf-8'))
    light = len(json_text.encode('utf-8'))
    print('[ok] index.html posts-data 已瘦身：%d 篇，数据块 %d B（原 %d B，省 %.1f%%）'
          % (len(posts), light, raw, 100 * (1 - light / raw)))


def first_page_html(posts):
    """生成首屏 6 张卡片的静态 HTML —— 浏览器流式解析到这里就能显示文章，
    不用等整份 HTML + JSON 下载完、也不用等 DOMContentLoaded 后 JS 渲染。
    JS 启动后 renderHome() 会用真实数据接管，视觉上无缝。"""
    import html as _html

    def e(v):
        return _html.escape(str(v or ''), quote=True)

    def fmt_date(d):
        return str(d or '').replace('-', '.')

    def read_time(words):
        mins = -(-int(words or 0) // 300)  # ceil
        return '< 1 分钟' if mins < 1 else '约 %d 分钟' % mins

    ordered = sorted(posts, key=lambda p: (not p.get('top', False),
                                           -int(p.get('pin') or 0),
                                           -int(p.get('id') or 0)))
    page = ordered[:6]
    cards = []
    for p in page:
        excerpt = plain_text(p.get('body', ''))[:100]
        if len(plain_text(p.get('body', ''))) > 100:
            excerpt += '…'
        badges = ('<span class="badge-top">📌 置顶</span>' if p.get('top') else '') + \
                 ('<span class="badge-priv">📋 草稿</span>' if p.get('draft') else '')
        tags = ''.join('<span class="tag" style="font-size:.76rem;padding:.1rem .5rem">%s</span>'
                       % e(t) for t in (p.get('tags') or [])[:2])
        cover = ('<div class="post-card-cover"><img src="%s" alt="缩略图"></div>' % e(p['thumb'])
                 if p.get('thumb') else
                 '<div class="post-card-cover">%s</div>' % e(p.get('cover') or '📝'))
        cards.append(
            '<div class="post-card" onclick="openPost(%s)">' % e(p.get('id'))
            + cover
            + '<div class="post-card-body"><div class="post-meta">'
            + '<span class="post-cat">%s</span>' % e(p.get('cat') or '随笔')
            + '<span class="post-date">📅 %s</span>' % e(fmt_date(p.get('date')))
            + badges
            + '</div><h3>%s</h3><p>%s</p></div>' % (e(p.get('title')), e(excerpt))
            + '<div class="post-footer">'
            + '<span class="post-stat">👁️ %d</span>' % int(p.get('views') or 0)
            + '<span class="post-stat">💬 0</span>'
            + '<span class="post-stat">📖 %s</span>' % e(read_time(word_count(p.get('body', ''))))
            + tags + '</div></div>'
        )
    return ''.join(cards)


def update_first_page(posts):
    """把首屏静态卡片写进 #posts-container（用注释标记包裹，便于每次构建覆盖）。"""
    html = open(INDEX, encoding='utf-8').read()
    start, end = '<!--FIRST_PAGE_START-->', '<!--FIRST_PAGE_END-->'
    cards = first_page_html(posts)
    if start in html and end in html:
        a = html.index(start) + len(start)
        b = html.index(end)
        html = html[:a] + '\n' + cards + '\n' + html[b:]
    else:
        tag = '<div id="posts-container" class="posts-grid"></div>'
        if tag not in html:
            print('[warn] 找不到 #posts-container，跳过首屏静态化')
            return
        html = html.replace(tag, '<div id="posts-container" class="posts-grid">'
                            + start + '\n' + cards + '\n' + end + '</div>', 1)
    open(INDEX, 'w', encoding='utf-8').write(html)
    print('[ok] 首屏静态卡片已生成（%d 篇）' % min(6, len(posts)))


def render_bodies(posts, md2html_src):
    tmp_in = os.path.join(HERE, '_posts_in.json')
    tmp_out = os.path.join(HERE, '_rendered.json')
    json.dump(posts, open(tmp_in, 'w', encoding='utf-8'), ensure_ascii=False)
    render_js = os.path.join(HERE, '_render.js')
    js = (
        "const fs=require('fs');\n"
        + md2html_src + "\n"
        + "const posts=JSON.parse(fs.readFileSync(" + json.dumps(tmp_in) + ",'utf8'));\n"
        + "const out={};\n"
        + "posts.forEach(p=>{ out[String(p.id)] = (typeof md2html==='function'? md2html(p.body||'') : ''); });\n"
        + "fs.writeFileSync(" + json.dumps(tmp_out) + ", JSON.stringify(out));\n"
    )
    open(render_js, 'w', encoding='utf-8').write(js)
    subprocess.run([NODE, render_js], check=True)
    return json.load(open(tmp_out, encoding='utf-8'))


def rfc822(d):
    try:
        dt = datetime.datetime.strptime(d, '%Y-%m-%d')
    except Exception:
        dt = datetime.datetime.utcnow()
    return dt.strftime('%a, %d %b %Y 00:00:00 GMT')


def esc_xml(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build_feed(posts, rendered):
    items = []
    for p in posts:
        pid = p.get('id')
        title = p.get('title', '')
        cat = p.get('cat', '')
        date = p.get('date', '')
        link = SITE + 'blog_posts/post_' + str(pid) + '.html'
        body_html = rendered.get(str(pid), '')
        item = (
            '    <item>\n'
            '    <title>' + esc_xml(title) + '</title>\n'
            '    <link>' + link + '</link>\n'
            '    <guid isPermaLink="true">' + link + '</guid>\n'
            '    <pubDate>' + rfc822(date) + '</pubDate>\n'
            '    <category>' + esc_xml(cat) + '</category>\n'
            '    <description><![CDATA[' + title + ']]></description>\n'
            '    <content:encoded><![CDATA[' + body_html + ']]></content:encoded>\n'
            '    </item>\n'
        )
        items.append(item)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        '  <channel>\n'
        '    <title>池帅の亦殿</title>\n'
        '    <link>' + SITE + '</link>\n'
        '    <atom:link href="' + SITE + 'feed.xml" rel="self" type="application/rss+xml"/>\n'
        '    <description>池帅的个人博客，记录生活，分享美好</description>\n'
        '    <language>zh-CN</language>\n'
        '    <lastBuildDate>' + now + '</lastBuildDate>\n'
        '    <generator>WorkBuddy RSS Generator</generator>\n'
        '    <image>\n'
        '      <url>' + SITE + 'favicon.ico</url>\n'
        '      <title>池帅の亦殿</title>\n'
        '      <link>' + SITE + '</link>\n'
        '    </image>\n'
        + ''.join(items) +
        '  </channel>\n'
        '</rss>\n'
    )
    open(FEED, 'w', encoding='utf-8').write(xml)
    print('[ok] feed.xml 已重建，条目数 =', len(items))


def compute_build(posts, bump=False):
    """build 号 = 最新文章日期-最新id-总篇数（内容不变则不变，保证幂等）"""
    latest = max(posts, key=lambda p: (str(p.get('date') or ''), p.get('id') or 0))
    bid = '%s-%s-%d' % (
        str(latest.get('date') or '1970-01-01').replace('-', ''),
        latest.get('id'),
        len(posts),
    )
    if bump:
        bid += '-' + datetime.datetime.now().strftime('%H%M%S')
    return bid, latest


def update_build_version(posts, bump=False):
    """每次构建同步维护版本三件套：version.json + index.html 的 blog-build meta + sw.js 缓存名。

    前端 index.html 靠轮询 version.json 的 build 判断是否有新文章，不一致就强制重载；
    sw.js 的 CACHE_NAME 随 build 变化 → 浏览器认为 SW 已更新 → 清掉旧缓存。
    三步齐备，页面才能在每天发文后自己刷新，而不是停留在昨天的内容。
    """
    bid, latest = compute_build(posts, bump)

    info = {
        'version': bid,
        'build': bid,
        'latestId': latest.get('id'),
        'latestDate': latest.get('date'),
        'latestTitle': latest.get('title', ''),
        'count': len(posts),
        'buildTime': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
    }
    json.dump(info, open(VERSION, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    html = open(INDEX, encoding='utf-8').read()
    tag = '<meta name="blog-build" content="%s">' % bid
    if re.search(r'<meta name="blog-build"[^>]*>', html):
        html = re.sub(r'<meta name="blog-build"[^>]*>', lambda m: tag, html, count=1)
    else:
        m = re.search(r'<title>.*?</title>', html, re.S)
        if not m:
            raise RuntimeError('找不到 <title>，无法注入 blog-build meta')
        html = html[:m.end()] + '\n\n' + tag + html[m.end():]
    open(INDEX, 'w', encoding='utf-8').write(html)

    sw = open(SW, encoding='utf-8').read()
    sw_new = re.sub(r"const CACHE_NAME = '[^']*';",
                    lambda m: "const CACHE_NAME = 'blog-v3-%s';" % bid, sw, count=1)
    if sw_new != sw:
        open(SW, 'w', encoding='utf-8').write(sw_new)

    print('[ok] build =', bid, '（version.json / index.html meta / sw.js 缓存名 已同步）')
    return bid


def main():
    posts = load_posts()
    html = open(INDEX, encoding='utf-8').read()
    md2html_src = extract_md2html(html)
    update_index_block(posts)
    update_first_page(posts)
    rendered = render_bodies(posts, md2html_src)
    build_feed(posts, rendered)
    update_build_version(posts, bump=('--bump' in sys.argv))
    # 清理临时文件
    for f in ('_posts_in.json', '_rendered.json', '_render.js'):
        try:
            os.remove(os.path.join(HERE, f))
        except OSError:
            pass
    print('[done] 全部生成完成。记得 git add -A && git commit && git push')


if __name__ == '__main__':
    main()
