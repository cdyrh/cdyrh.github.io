#!/usr/bin/env python3
"""修复所有 blog_posts/ 和 posts/ HTML 文件中 toc-list <ul> 缺少 id 属性的 bug。

根因：<ul class="toc-list"> 没有 id="toc-list"
      buildTOC_legacy() 使用 document.getElementById('toc-list') → 返回 null
      → tocList.innerHTML = '' 抛 TypeError → TOC 永远无法动态重建
"""
import os
import re
import glob

BASE = os.path.dirname(os.path.abspath(__file__))

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 模式: <ul class="toc-list"> (没有 id 属性)
    # 替换为: <ul class="toc-list" id="toc-list">
    old = '<ul class="toc-list">'
    new = '<ul class="toc-list" id="toc-list">'

    if old not in content:
        return False

    # 确保不是已经修复过的
    if '<ul class="toc-list" id="toc-list">' in content:
        return False

    content = content.replace(old, new, 1)  # 只替换第一个出现
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return True

def main():
    dirs = ['blog_posts', 'posts']
    fixed_count = 0

    for d in dirs:
        pattern = os.path.join(BASE, d, '*.html')
        for filepath in sorted(glob.glob(pattern)):
            if fix_file(filepath):
                rel = os.path.relpath(filepath, BASE)
                print(f'  ✅ 已修复: {rel}')
                fixed_count += 1
            else:
                rel = os.path.relpath(filepath, BASE)
                # 检查是否已经修复
                with open(filepath, 'r', encoding='utf-8') as f:
                    if 'id="toc-list"' in f.read():
                        print(f'  ⏭ 已修复过: {rel}')
                    else:
                        print(f'  ❌ 未找到 toc-list: {rel}')

    print(f'\n总计修复 {fixed_count} 个文件')

if __name__ == '__main__':
    main()
