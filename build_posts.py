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


def update_index_block(posts):
    html = open(INDEX, encoding='utf-8').read()
    json_text = json.dumps(posts, ensure_ascii=False).replace('<', '\\u003c')
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
    print('[ok] index.html posts-data 块已更新，文章数 =', len(posts))


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


def main():
    posts = load_posts()
    html = open(INDEX, encoding='utf-8').read()
    md2html_src = extract_md2html(html)
    update_index_block(posts)
    rendered = render_bodies(posts, md2html_src)
    build_feed(posts, rendered)
    # 清理临时文件
    for f in ('_posts_in.json', '_rendered.json', '_render.js'):
        try:
            os.remove(os.path.join(HERE, f))
        except OSError:
            pass
    print('[done] 全部生成完成。记得 git add -A && git commit && git push')


if __name__ == '__main__':
    main()
