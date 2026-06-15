#!/usr/bin/env python3
"""
修复 posts/ 目录: 在 buildTOC_legacy 定义后添加调用。
"""

import os
import glob

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    old = "    // TOC已改为静态HTML\n    </script>"
    new = "    buildTOC_legacy();\n    </script>"
    
    if old in content:
        content = content.replace(old, new)
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    return False

def main():
    posts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'posts')
    files = sorted(glob.glob(os.path.join(posts_dir, '*.html')))
    
    ok = sum(1 for f in files if fix_file(f))
    print(f"posts/ 目录: 添加 buildTOC_legacy() 调用: {ok}/{len(files)}")

if __name__ == '__main__':
    main()
