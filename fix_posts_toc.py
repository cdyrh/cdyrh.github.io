#!/usr/bin/env python3
"""
修复 posts/ 目录下所有文件的 TOC bug。
复用 blog_posts/ 目录的修复逻辑。
"""

import os
import glob
import re

def fix_return(files):
    """移除 buildTOC_legacy 中的 return;"""
    count = 0
    for f in files:
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
        original = content
        old = r'function buildTOC_legacy\(\) \{ // 静态TOC已替代动态构建\n\s*return;\n'
        new = 'function buildTOC_legacy() { // 动态重建 TOC - 已修复\n'
        if re.search(old, content):
            content = re.sub(old, new, content)
            if content != original:
                with open(f, 'w', encoding='utf-8') as fh:
                    fh.write(content)
                count += 1
    return count

def fix_call(files):
    """在 DOMContentLoaded 中添加 buildTOC_legacy() 调用"""
    count = 0
    for f in files:
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
        original = content
        old = "  }\n});\n</script>"
        new = "  }\n  buildTOC_legacy();\n});\n</script>"
        if old in content:
            content = content.replace(old, new)
            if content != original:
                with open(f, 'w', encoding='utf-8') as fh:
                    fh.write(content)
                count += 1
        else:
            old2 = "}\n});\n</script>"
            new2 = "}\n  buildTOC_legacy();\n});\n</script>"
            if old2 in content:
                content = content.replace(old2, new2)
                if content != original:
                    with open(f, 'w', encoding='utf-8') as fh:
                        fh.write(content)
                    count += 1
    return count

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    posts_dir = os.path.join(base, 'posts')
    files = sorted(glob.glob(os.path.join(posts_dir, '*.html')))
    
    rc = fix_return(files)
    cc = fix_call(files)
    
    print(f"posts/ 目录: 移除 return; {rc} 个, 添加调用 {cc} 个, 共 {len(files)} 个文件")

if __name__ == '__main__':
    main()
