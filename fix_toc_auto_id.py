#!/usr/bin/env python3
"""
修复 buildTOC_legacy() 函数：自动为没有 id 属性的标题生成 ID。
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

OLD_LINE = "        a.href = '#' + h.id;"
NEW_CODE = """        // 自动生成 ID：如果标题没有 id，从文本内容生成
        var headingId = h.id;
        if (!headingId) {
          headingId = h.textContent.replace(/[^\\w\\u4e00-\\u9fff]/g, '').substring(0, 50);
          h.id = headingId;
        }
        a.href = '#' + headingId;"""

def find_files():
    files = []
    for d in ['blog_posts', 'posts']:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for f in sorted(os.listdir(dp)):
            if f.endswith('.html'):
                fp = os.path.join(dp, f)
                with open(fp, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                if 'buildTOC_legacy' in content:
                    files.append(fp)
    return files

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'headingId' in content:
        return 'already_fixed'

    if OLD_LINE not in content:
        return 'not_found'

    new_content = content.replace(OLD_LINE, NEW_CODE)
    
    # Verify the replacement actually changed something and is valid
    if new_content == content:
        return 'no_change'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return 'fixed'

def main():
    files = find_files()
    print(f"找到 {len(files)} 个包含 buildTOC_legacy 的文件\n")

    fixed = 0
    already = 0
    not_found = 0
    for fp in files:
        result = fix_file(fp)
        rel = os.path.relpath(fp, ROOT)
        if result == 'fixed':
            print(f"  ✅ {rel}")
            fixed += 1
        elif result == 'already_fixed':
            print(f"  ⏭ {rel} (已有 headingId)")
            already += 1
        else:
            print(f"  ⚠️ {rel} (未找到匹配行)")
            not_found += 1

    print(f"\n修复: {fixed}, 已有: {already}, 未匹配: {not_found}, 总计: {len(files)}")

if __name__ == '__main__':
    main()
