#!/usr/bin/env python3
"""
修复 2/2: 在 DOMContentLoaded 中调用 buildTOC_legacy()。
"""

import os
import glob

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # 在 DOMContentLoaded 回调的 }); 之前插入 buildTOC_legacy();
    # 目标:  } 后面是 }); 再后面是 </script>
    old = "  }\n});\n</script>"
    new = "  }\n  buildTOC_legacy();\n});\n</script>"
    
    count = content.count(old)
    if count == 0:
        # Try alternative indentation
        old = "}\n});\n</script>"
        new = "}\n  buildTOC_legacy();\n});\n</script>"
        count = content.count(old)

    if count == 1:
        content = content.replace(old, new)
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    elif count > 1:
        # Multiple matches - find the one right before the TOC section
        idx = content.find('// ======================== 文章目录 TOC ========================')
        if idx > 0:
            before = content[:idx]
            after = content[idx:]
            # Find last occurrence of old pattern before TOC
            last_idx = before.rfind(old)
            if last_idx > 0:
                before = before[:last_idx] + before[last_idx:].replace(old, new, 1)
                content = before + after
                if content != original:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return True
    return False

def main():
    blog_posts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blog_posts')
    files = glob.glob(os.path.join(blog_posts_dir, '*.html'))
    
    ok = 0
    for f in sorted(files):
        if fix_file(f):
            ok += 1
            print(f"  ✅ {os.path.basename(f)}")
        else:
            print(f"  ❌ {os.path.basename(f)}")
    
    print(f"\n总计: {ok}/{len(files)}")

if __name__ == '__main__':
    main()
