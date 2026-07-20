#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new_post.py —— 安全追加新文章到 posts_data.json（永久修复配套工具）

用法:
    python new_post.py article.json

article.json 是一个文章对象，例如:
    {
      "id": 58,
      "top": true,
      "pin": 115,
      "title": "标题",
      "cat": "分类",
      "tags": ["标签1", "标签2"],
      "cover": "✨",
      "date": "2026-07-20",
      "views": 0,
      "body": "markdown 正文纯文本（不要反引号模板字符串、不要 ${）"
    }

本脚本把对象追加到 posts_data.json 数组末尾，并保持紧凑 JSON 格式。
它会做基本校验（必填字段、ID 不重复），绝不会产生破坏性的手写拼接。
追加后请运行 build_posts.py 重建 index.html 与 feed.xml。
"""
import json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'posts_data.json')


def main():
    if len(sys.argv) < 2:
        print("用法: python new_post.py <article.json>")
        sys.exit(1)
    path = sys.argv[1]
    try:
        new = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        print("❌ 文章 JSON 解析失败:", e)
        sys.exit(1)

    for k in ('id', 'title', 'body'):
        if k not in new:
            print("❌ 文章缺少必填字段:", k)
            sys.exit(1)

    posts = json.load(open(DATA, encoding='utf-8'))
    ids = {p.get('id') for p in posts}
    if new['id'] in ids:
        print("❌ ID %s 已存在，拒绝追加（避免重复导致显示异常）" % new['id'])
        sys.exit(1)

    posts.append(new)
    # 保持紧凑格式（与现有 posts_data.json 一致，避免无谓的大 diff）
    json.dump(posts, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False)
    print("✅ 已追加 id=%s 标题=%r，当前共 %d 篇" % (new['id'], new['title'][:30], len(posts)))


if __name__ == '__main__':
    main()
