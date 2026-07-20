#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new_post.py —— 安全追加新文章到 posts_data.json（永久修复配套工具）

两种用法：

A) 从现成 JSON 文件追加（字段需自己保证合法 JSON）:
    python new_post.py article.json

B) 推荐用法：正文走 .md 文件，其余字段走参数（脚本用 json.dump 组装，
   正文里的反引号 / ${} / 反斜杠 / 引号 全部无需手动转义，绝不会破坏 JSON）:
    python new_post.py --id 58 --title "标题" --cat "生活常识" \
        --tags "标签1,标签2" --cover "✨" --date 2026-07-20 --pin 115 \
        --body-file body_1.md

字段说明（posts_data.json 单篇文章对象）:
    id      必填，整数，全局唯一、不重复
    title   必填，字符串
    cat     分类，字符串
    tags    标签，逗号分隔字符串（--tags "a,b"）或 JSON 数组（article.json 模式）
    cover   emoji 封面，字符串
    date    YYYY-MM-DD
    pin     置顶权重，整数（越大越靠前）
    top     固定为 true
    views   0
    body    正文（markdown 纯文本；用 --body-file 时直接读 .md 文件内容）

追加后请运行 build_posts.py 重建 index.html 与 feed.xml。
"""
import json, sys, os, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'posts_data.json')


def load_posts():
    return json.load(open(DATA, encoding='utf-8'))


def save_posts(posts):
    # 保持紧凑格式（与现有 posts_data.json 一致，避免无谓的大 diff）
    json.dump(posts, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False)


def build_from_args(args):
    body = ''
    if args.body_file:
        body = open(args.body_file, encoding='utf-8').read()
    elif args.body:
        body = args.body
    tags = []
    if args.tags:
        # 兼容 JSON 数组字符串与逗号分隔
        try:
            parsed = json.loads(args.tags)
            if isinstance(parsed, list):
                tags = [str(t) for t in parsed]
            else:
                tags = [args.tags]
        except Exception:
            tags = [t.strip() for t in args.tags.split(',') if t.strip()]
    return {
        'id': args.id,
        'top': True,
        'pin': args.pin if args.pin is not None else 0,
        'title': args.title,
        'cat': args.cat or '随笔',
        'tags': tags,
        'cover': args.cover or '✨',
        'date': args.date,
        'views': 0,
        'body': body,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('jsonfile', nargs='?', help='现成 article.json 路径')
    ap.add_argument('--id', type=int)
    ap.add_argument('--title')
    ap.add_argument('--cat')
    ap.add_argument('--tags', help='逗号分隔或 JSON 数组字符串')
    ap.add_argument('--cover')
    ap.add_argument('--date')
    ap.add_argument('--pin', type=int, default=0)
    ap.add_argument('--body', help='正文（字符串，少用；优先 --body-file）')
    ap.add_argument('--body-file', help='正文 markdown 文件路径（推荐）')
    args = ap.parse_args()

    if args.jsonfile:
        try:
            new = json.load(open(args.jsonfile, encoding='utf-8'))
        except Exception as e:
            print("❌ 文章 JSON 解析失败:", e)
            sys.exit(1)
    else:
        if not args.id or not args.title:
            print("❌ 需提供 --id 和 --title，或传入 article.json")
            sys.exit(1)
        new = build_from_args(args)

    for k in ('id', 'title', 'body'):
        if k not in new or new.get(k) in (None, ''):
            print("❌ 文章缺少必填字段或内容为空:", k)
            sys.exit(1)

    posts = load_posts()
    ids = {p.get('id') for p in posts}
    if new['id'] in ids:
        print("❌ ID %s 已存在，拒绝追加（避免重复导致显示异常）" % new['id'])
        sys.exit(1)

    posts.append(new)
    save_posts(posts)
    print("✅ 已追加 id=%s 标题=%r，当前共 %d 篇" % (new['id'], str(new['title'])[:30], len(posts)))


if __name__ == '__main__':
    main()
