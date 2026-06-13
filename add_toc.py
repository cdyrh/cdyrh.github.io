#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为博客文章添加目录导航功能
- 为所有h2和h3标题添加id属性
- 添加目录导航的HTML结构
- 添加buildTOC()函数
"""

import re
import os
import sys

def slugify(text):
    """将标题文本转换为id（简单的拼音/ASCII转换）"""
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 转换为ASCII（如果是中文，使用简单的方法）
    # 这里我们使用一个简单的映射表，或者使用标题的索引作为id
    return text.strip()

def add_toc_to_html(file_path):
    """为单个HTML文件添加目录导航功能"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 为所有h2和h3标题添加id属性
    heading_counter = {}
    
    def add_id_to_heading(match):
        tag = match.group(1)  # h2 or h3
        attrs = match.group(2)  # 现有属性
        title = match.group(3)  # 标题文本
        
        # 生成id：使用标题文本的简化版本
        # 移除HTML标签
        clean_title = re.sub(r'<[^>]+>', '', title)
        # 转换为适合作为id的格式
        heading_id = re.sub(r'[^\w\s-]', '', clean_title)
        heading_id = re.sub(r'\s+', '-', heading_id)
        heading_id = heading_id.lower()
        
        # 如果id为空，使用默认id
        if not heading_id:
            heading_id = f'{tag}-{len(heading_counter)}'
        
        # 确保id唯一
        if heading_id in heading_counter:
            heading_counter[heading_id] += 1
            heading_id = f'{heading_id}-{heading_counter[heading_id]}'
        else:
            heading_counter[heading_id] = 0
        
        return f'<{tag} id="{heading_id}" {attrs}>{title}</{tag}>'
    
    # 匹配<h2>或<h3>标签（可能没有属性）
    pattern = r'<(h[23])([^>]*)>(.*?)</\1>'
    content = re.sub(pattern, add_id_to_heading, content, flags=re.DOTALL)
    
    # 2. 在<p class="post-body">或<div class="post-body">之前添加目录导航HTML结构
    toc_html = '''
    <!-- TOC 目录导航 -->
    <div class="toc-box" id="toc-box" style="display:none">
      <div class="toc-title">📋 文章目录</div>
      <ul class="toc-list" id="toc-list"></ul>
    </div>
    '''
    
    # 在post-body div之前插入TOC
    pattern = r'(<div class="post-body"[^>]*>)'
    if re.search(pattern, content):
        content = re.sub(pattern, toc_html + r'\1', content, count=1)
    
    # 3. 添加CSS样式（如果还没有的话）
    toc_css = '''
    <style>
    /* ===== TOC (文章目录) ===== */
    .toc-box {
      background: var(--pink-pale, #fff0f5);
      border-radius: 10px;
      border: 1.5px solid var(--border, #f0d9ff);
      padding: 1rem 1.2rem;
      margin-bottom: 1.5rem;
    }
    .toc-title {
      font-weight: 700;
      color: var(--pink-deep, #e85d8a);
      margin-bottom: 0.6rem;
      font-size: 0.92rem;
    }
    .toc-list {
      list-style: none;
      padding: 0;
    }
    .toc-list li {
      line-height: 2;
    }
    .toc-list a {
      color: var(--text-light, #7c6f9f);
      text-decoration: none;
      font-size: 0.88rem;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      display: block;
      transition: all 0.15s;
    }
    .toc-list a:hover {
      color: var(--pink-deep, #e85d8a);
      background: rgba(255, 143, 171, 0.1);
    }
    .toc-list .toc-h3 {
      padding-left: 1.2rem;
      font-size: 0.84rem;
    }
    </style>
    '''
    
    # 在</head>之前插入CSS
    if '</head>' in content and 'toc-box' not in content[:content.find('</head>') + 100]:
        content = content.replace('</head>', toc_css + '\n</head>', 1)
    
    # 4. 添加JavaScript函数
    toc_js = '''
    <script>
    // ======================== 文章目录 TOC ========================
    function buildTOC() {
      // 查找文章内容区域
      var body = document.getElementById('post-body');
      if (!body) return;
      
      // 查找所有h2和h3标题
      var headings = body.querySelectorAll('h2, h3');
      var tocBox = document.getElementById('toc-box');
      var tocList = document.getElementById('toc-list');
      
      // 如果标题少于2个，隐藏目录
      if (headings.length < 2) {
        if (tocBox) tocBox.style.display = 'none';
        return;
      }
      
      // 显示目录
      if (tocBox) tocBox.style.display = 'block';
      
      // 构建目录HTML
      var tocHTML = '';
      for (var i = 0; i < headings.length; i++) {
        var h = headings[i];
        var level = h.tagName === 'H3' ? 'toc-h3' : '';
        var id = h.id;
        var text = h.textContent;
        
        tocHTML += '<li class="' + level + '"><a href="#' + id + '" onclick="event.preventDefault();var el=document.getElementById(\'' + id + '\');if(el){el.scrollIntoView({behavior:\'smooth\'});}return false;">' + text + '</a></li>';
      }
      
      if (tocList) tocList.innerHTML = tocHTML;
    }
    
    // 页面加载完成后构建目录
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', buildTOC);
    } else {
      buildTOC();
    }
    </script>
    '''
    
    # 在</body>之前插入JavaScript
    if '</body>' in content:
        content = content.replace('</body>', toc_js + '\n</body>', 1)
    else:
        # 如果没有</body>，在文件末尾添加
        content += toc_js
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'已处理: {file_path}')

def main():
    # 处理blog_posts/目录下的所有HTML文件
    blog_posts_dir = 'blog_posts'
    if not os.path.exists(blog_posts_dir):
        print(f'目录不存在: {blog_posts_dir}')
        return
    
    count = 0
    for filename in os.listdir(blog_posts_dir):
        if filename.endswith('.html'):
            file_path = os.path.join(blog_posts_dir, filename)
            try:
                add_toc_to_html(file_path)
                count += 1
            except Exception as e:
                print(f'处理失败 {file_path}: {e}')
    
    print(f'\n总共处理了 {count} 个文件')

if __name__ == '__main__':
    # 切换到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir:
        os.chdir(script_dir)
    
    main()
