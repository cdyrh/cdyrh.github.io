#!/usr/bin/env python3
"""
为博客所有文章生成静态TOC（文章目录）+ 修复所有增强功能
- 生成静态HTML TOC（不依赖JavaScript）
- 计算字数和阅读时间
- 移除动态buildTOC（保留为fallback）
- 修复DOCTYPE问题
"""

import re
import os
import glob

BLOG_DIR = os.path.dirname(os.path.abspath(__file__))

def count_chinese_chars(text):
    return len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]', text))

def count_total_chars(text):
    return len(re.sub(r'\s', '', text))

def extract_headings(html, post_body_start, post_body_end):
    body_html = html[post_body_start:post_body_end]
    pattern = re.compile(r'<(h[23])\s+[^>]*?\bid\s*=\s*"([^"]*)"[^>]*?>\s*(.+?)\s*</\1>', re.DOTALL)
    headings = []
    for m in pattern.finditer(body_html):
        tag = m.group(1)
        id_val = m.group(2)
        text = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        if text:
            headings.append((tag, id_val, text))
    return headings

def generate_static_toc(headings):
    if len(headings) < 2:
        return None

    toc_html = '    <!-- TOC 文章目录 -->\n'
    toc_html += '    <div class="toc-box" id="toc-box">\n'
    toc_html += '      <div class="toc-title">📋 文章目录</div>\n'
    toc_html += '      <ul class="toc-list" id="toc-list">\n'

    for tag, id_val, text in headings:
        cls = ' class="toc-h3"' if tag == 'h3' else ''
        toc_html += f'        <li{cls}><a href="#{id_val}">{text}</a></li>\n'

    toc_html += '      </ul>\n'
    toc_html += '    </div>'
    return toc_html

def generate_reading_stats(body_html):
    text = re.sub(r'<[^>]+>', '', body_html)
    text = re.sub(r'&[a-z]+;', ' ', text)
    total_chars = count_total_chars(text)
    read_min = max(1, round(total_chars / 400))

    return f"""    <!-- 阅读统计 -->
    <div class="reading-stats" id="reading-stats">
      <span>📝 字数：<strong id="word-count">{total_chars:,}</strong></span>
      <span>⏱ 阅读：<strong id="read-time">约 {read_min} 分钟</strong></span>
    </div>"""

def find_post_body_range(html):
    start_match = re.search(r'<div\s+class="(?:post-body|article-body)"\s+id="post-body"\s*>', html)
    if not start_match:
        return None, None

    start_pos = start_match.end()
    depth = 1
    pos = start_pos
    while depth > 0 and pos < len(html):
        next_open = html.find('<div', pos)
        next_close = html.find('</div>', pos)

        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6

    if depth == 0:
        return start_match.start(), pos
    return None, None

def find_toc_section(html):
    """找到TOC区域（处理嵌套div）"""
    comment_match = re.search(r'<!--\s*TOC\s+.*?-->', html)
    if not comment_match:
        return None, None

    after_comment = html[comment_match.end():]
    div_match = re.search(r'<div\s+class="toc-box"[^>]*\bid="toc-box"[^>]*>', after_comment)
    if not div_match:
        return None, None

    toc_start = comment_match.start()
    pos = comment_match.end() + div_match.end()

    # 计数嵌套div来找到toc-box的结束</div>
    depth = 1
    i = pos
    while i < len(html) and depth > 0:
        next_open = html.find('<div', i)
        next_close = html.find('</div>', i)

        if next_close == -1:
            return None, None

        if next_open != -1 and next_open < next_close:
            depth += 1
            i = next_open + 4
        else:
            depth -= 1
            i = next_close + 6

    if depth == 0:
        before = html.rfind('\n', 0, toc_start)
        before = before if before != -1 else toc_start
        after = html.find('\n', i)
        after = after if after != -1 else i
        return before + 1, after

    return None, None

def find_reading_stats_section(html):
    pattern = re.compile(
        r'(\s*<!--\s*阅读统计\s*-->\s*\n'
        r'\s*<div\s+class="reading-stats"[^>]*>.*?'
        r'</div>\s*)',
        re.DOTALL
    )
    m = pattern.search(html)
    if m:
        return m.start(), m.end()
    return None, None

def fix_reading_stats_script(html):
    pattern = re.compile(
        r'\n\s*//\s*=+\s*阅读统计\s*=+\s*\n'
        r'\s*\(function\s+calcStats\(\)\s*\{.*?\}\)\(\);\s*',
        re.DOTALL
    )
    return pattern.sub('\n', html)

def fix_file(filepath):
    print(f"Processing: {os.path.basename(filepath)}")

    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Fix DOCTYPE
    if not html.strip().startswith('<!DOCTYPE html>'):
        html = re.sub(r'^.*?(?=<!DOCTYPE)', '', html, count=1, flags=re.DOTALL)
        if not html.startswith('<!DOCTYPE html>'):
            html = '<!DOCTYPE html>\n' + re.sub(r'^.*?<html', '<html', html, count=1, flags=re.DOTALL)

    # 2. Find post-body
    body_start, body_end = find_post_body_range(html)
    if body_start is None:
        print(f"  WARNING: Could not find post-body div")
        return False

    body_html = html[body_start:body_end]

    # 3. Extract headings
    headings = extract_headings(html, body_start, body_end)
    print(f"  Found {len(headings)} headings")

    # 4. Replace TOC section
    toc_start, toc_end = find_toc_section(html)
    if toc_start is not None:
        static_toc = generate_static_toc(headings)
        if static_toc:
            html = html[:toc_start] + static_toc + '\n' + html[toc_end:]
            print(f"  TOC: Static with {len(headings)} items")
        else:
            after_toc = html[toc_end:].lstrip()
            html = html[:toc_start] + '\n' + after_toc
            print(f"  TOC: Removed (only {len(headings)} heading)")
    else:
        print(f"  TOC: Not found in file")

    # 5. Replace reading stats
    rs_start, rs_end = find_reading_stats_section(html)
    if rs_start is not None:
        body_start2, body_end2 = find_post_body_range(html)
        if body_start2:
            body_html2 = html[body_start2:body_end2]
            new_stats = generate_reading_stats(body_html2)
            html = html[:rs_start] + new_stats + '\n' + html[rs_end:]
            print(f"  Stats: Updated")

    # 6. Ensure buildTOC_legacy() works (fix old naming / add auto-ID)
    html = html.replace(
        'function buildTOC() {',
        'function buildTOC_legacy() { // 动态重建TOC（已修复：移除return，自动生成id）'
    )
    # 确保 DOMContentLoaded 中调用了 buildTOC_legacy()
    if 'buildTOC_legacy()' not in html:
        # 如果没有调用，在脚本末尾添加
        html = re.sub(
            r'(</script>\s*</body>)',
            r"<script>document.addEventListener('DOMContentLoaded', function() { if (typeof buildTOC_legacy === 'function') buildTOC_legacy(); });</script>\n\1",
            html
        )

    # 7. Clean up stray HTML
    html = re.sub(r'\n\s*<div\s*\n(\s*)<!-- 留言区 -->', r'\n\1<!-- 留言区 -->', html)
    html = re.sub(r'(?<!\w)\s{4}class="back-home"', '    <div class="back-home"', html)

    # 8. Remove dynamic reading stats script
    html = fix_reading_stats_script(html)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    return True

def main():
    patterns = [
        os.path.join(BLOG_DIR, 'blog_posts', 'post_*.html'),
        os.path.join(BLOG_DIR, 'posts', 'post_*.html'),
    ]

    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    files = sorted(set(files))
    print(f"Found {len(files)} article files\n")

    success = 0
    for f in files:
        if fix_file(f):
            success += 1
        print()

    print(f"Done! Fixed {success}/{len(files)} files.")

if __name__ == '__main__':
    main()
