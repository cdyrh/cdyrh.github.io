#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复TOC JavaScript代码中的语法错误
"""

import os
import re

def fix_toc_js(file_path):
    """修复单个HTML文件中的TOC JavaScript代码"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找并替换有问题的JavaScript代码
    # 原来的代码有引号嵌套问题，导致语法错误
    old_pattern = r"onclick=\"event\.preventDefault\(\);var el=document\.getElementById\('[^']+'\);if\(el\)\{el\.scrollIntoView\(\{behavior:'smooth'\}\);\}return false;\""
    
    # 新的代码：使用正确的引号转义
    def replace_onclick(match):
        # 提取id
        id_match = re.search(r"getElementById\('([^']+)'\)", match.group(0))
        if id_match:
            heading_id = id_match.group(1)
            # 生成新的onclick代码，使用转义引号
            new_onclick = f'''onclick="event.preventDefault();var el=document.getElementById('{heading_id}');if(el){{el.scrollIntoView({{behavior:'smooth'}});}}return false;"'''
            return new_onclick
        return match.group(0)
    
    # 由于正则表达式可能不够准确，我们直接替换整个buildTOC函数
    # 查找buildTOC函数
    toc_js_pattern = r'<script>\s*// ======================== 文章目录 TOC ========================\s*function buildTOC\(\) \{.*?</script>'
    
    def replace_toc_js(match):
        # 生成新的buildTOC函数，使用正确的引号
        new_js = '''
    <script>
    // ======================== 文章目录 TOC ========================
    function buildTOC() {
      var body = document.getElementById('post-body');
      if (!body) return;
      var headings = body.querySelectorAll('h2, h3');
      var tocBox = document.getElementById('toc-box');
      var tocList = document.getElementById('toc-list');
      if (headings.length < 2) {
        if (tocBox) tocBox.style.display = 'none';
        return;
      }
      if (tocBox) tocBox.style.display = 'block';
      var tocHTML = '';
      for (var i = 0; i < headings.length; i++) {
        var h = headings[i];
        var level = h.tagName === 'H3' ? 'toc-h3' : '';
        var id = h.id;
        var text = h.textContent;
        // 使用闭包来避免引号问题
        tocHTML += '<li class="' + level + '"><a href="#' + id + '" onclick="scrollToHeading(\\' + id + '\\')">' + text + '</a></li>';
      }
      if (tocList) tocList.innerHTML = tocHTML;
    }
    
    function scrollToHeading(id) {
      var el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({behavior: 'smooth'});
      }
      return false;
    }
    
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', buildTOC);
    } else {
      buildTOC();
    }
    </script>
    '''
        return new_js
    
    # 替换buildTOC函数
    content = re.sub(toc_js_pattern, replace_toc_js, content, flags=re.DOTALL)
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'已修复: {file_path}')

def main():
    # 修复blog_posts/目录下的所有HTML文件
    blog_posts_dir = 'blog_posts'
    count = 0
    for filename in os.listdir(blog_posts_dir):
        if filename.endswith('.html'):
            file_path = os.path.join(blog_posts_dir, filename)
            try:
                fix_toc_js(file_path)
                count += 1
            except Exception as e:
                print(f'修复失败 {file_path}: {e}')
    
    # 修复posts/目录下的所有HTML文件
    posts_dir = 'posts'
    for filename in os.listdir(posts_dir):
        if filename.endswith('.html'):
            file_path = os.path.join(posts_dir, filename)
            try:
                fix_toc_js(file_path)
                count += 1
            except Exception as e:
                print(f'修复失败 {file_path}: {e}')
    
    print(f'\n总共修复了 {count} 个文件')

if __name__ == '__main__':
    # 切换到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir:
        os.chdir(script_dir)
    
    main()
