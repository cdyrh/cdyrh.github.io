#!/usr/bin/env python3
"""
修复 blog_posts HTML 文件的文章目录（TOC）点击无效 bug。

问题：
1. buildTOC_legacy() 被 return; 禁用（注释说"静态TOC已替代动态构建"）
2. 静态 TOC 链接来自错误模板，与实际标题 id 完全不匹配
3. buildTOC_legacy() 即使解除 return 也从未被调用

修复：
1. 移除 return; 启用动态 TOC 重建
2. 在 DOMContentLoaded 中调用 buildTOC_legacy()
"""

import os
import glob
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    changes = []

    # --- 修复 1: 移除 return; ---
    old_pattern = r'function buildTOC_legacy\(\) \{ // 静态TOC已替代动态构建\n\s*return;\n'
    new_text = 'function buildTOC_legacy() { // 动态重建 TOC - 已修复\n'
    if re.search(old_pattern, content):
        content = re.sub(old_pattern, new_text, content)
        changes.append("移除 return;")

    # --- 修复 2: 在 DOMContentLoaded 中调用 buildTOC_legacy() ---
    # 匹配 DOMContentLoaded 闭包的结尾 }); 后面跟着 </script>，并且在 buildTOC_legacy 定义之前
    # 精确策略：在 DOMContentLoaded handler 的 }); 后面加 buildTOC_legacy();
    dom_pattern = r"(window\.addEventListener\('DOMContentLoaded',\s*function\(\s*\)\s*\{[^}]*highlightElement[^}]*\}\s*\);\s*\}\s*\);)"
    replacement = r"\1\n  buildTOC_legacy();"
    
    if re.search(dom_pattern, content, re.DOTALL):
        new_content = re.sub(dom_pattern, replacement, content, flags=re.DOTALL)
        if new_content != content:
            content = new_content
            changes.append("添加 buildTOC_legacy() 调用")
    else:
        # Try alternative pattern for files with different DOMContentLoaded structure
        alt_pattern = r"(window\.addEventListener\('DOMContentLoaded',\s*function\s*\(\)\s*\{)"
        if re.search(alt_pattern, content):
            # Find the closing of this handler and add call before it
            pass  # Will handle with more specific approach below
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, ", ".join(changes)
    return False, "无变化"

def main():
    blog_posts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blog_posts')
    pattern = os.path.join(blog_posts_dir, '*.html')
    files = glob.glob(pattern)

    fixed_count = 0
    skipped_count = 0

    for f in sorted(files):
        basename = os.path.basename(f)
        success, reason = fix_file(f)
        if success:
            print(f"  ✅ {basename}: {reason}")
            fixed_count += 1
        else:
            print(f"  ⏭️  {basename}: {reason}")
            skipped_count += 1

    print(f"\n总计: 修复 {fixed_count} 个, 跳过 {skipped_count} 个 (共 {len(files)} 个文件)")

if __name__ == '__main__':
    main()
