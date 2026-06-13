#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量修复TOC JavaScript代码中的语法错误
"""

import os
import re

def fix_toc_js_in_file(file_path):
    """修复单个HTML文件中的TOC JavaScript代码"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找并替换有问题的onclick代码行
    # 旧代码：onclick="event.preventDefault();var el=document.getElementById('id');if(el){el.scrollIntoView({behavior:'smooth'});}return false;"
    # 新代码：onclick="event.preventDefault();scrollToHeading('id')"
    
    # 使用正则表达式查找并替换整行
    pattern = r"tocHTML \+= '<li class=\"' \+ level \+ '\"'><a href=\"#' \+ id \+ '\" onclick=\"[^\"]+\">' \+ text \+ '</a></li>';"
    
    def replace_line(match):
        # 生成新的代码行，使用scrollToHeading函数
        new_line = '''tocHTML += '<li class="' + level + '"><a href="#" + id + '" onclick="event.preventDefault();scrollToHeading(\\'' + id + '\\')">' + text + '</a></li>';'''
        return new_line
    
    # 由于正则表达式可能不准确，我们直接替换整个buildTOC函数
    # 查找buildTOC函数和后面的scrollToHeading函数（如果有的话）
    
    # 旧的buildTOC函数模式
    old_build_toc_pattern = r"function buildTOC\(\) \{[^}]+\}[^}]+\}[^}]+\}[^}]+\}"
    
    # 新的、正确的buildTOC函数和scrollToHeading函数
    new_toc_js = '''
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
        tocHTML += '<li class="' + level + '"><a href="#' + id + '" onclick="event.preventDefault();scrollToHeading(\\'' + id + '\\')">' + text + '</a></li>';
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
    '''
    
    # 替换整个script块（包含buildTOC函数）
    script_pattern = r'<script>\s*// ======================== 文章目录 TOC ========================.*?</script>'
    
    if re.search(script_pattern, content, re.DOTALL):
        content = re.sub(script_pattern, new_toc_js, content, flags=re.DOTALL)
    else:
        # 如果没有找到，在</body>之前添加
        if '</body>' in content:
            content = content.replace('</body>', new_toc_js + '\n</body>')
    
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
                fix_toc_js_in_file(file_path)
                count += 1
            except Exception as e:
                print(f'修复失败 {file_path}: {e}')
    
    # 修复posts/目录下的所有HTML文件
    posts_dir = 'posts'
    for filename in os.listdir(posts_dir):
        if filename.endswith('.html'):
            file_path = os.path.join(posts_dir, filename)
            try:
                fix_toc_js_in_file(file_path)
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
