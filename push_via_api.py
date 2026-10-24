#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push_via_api.py —— 走 GitHub Git Data API 一次性提交多个文件

为什么用它：本机网络只能连通 api.github.com，github.com:443 的 git 传输被拦
（CONNECT tunnel failed / 502），git push 必然失败。

流程：取远端 main 的 head commit → 为每个文件建 blob → 基于远端 tree 建新 tree
→ 建 commit → 快进 refs/heads/main。等价于一次正常 push，但只走 API。

用法：
    GITHUB_TOKEN=ghp_xxx python push_via_api.py "提交说明" 文件1 文件2 ...
"""
import base64, json, os, sys, urllib.request, urllib.error

OWNER, REPO = 'cdyrh', 'cdyrh.github.io'
API = 'https://api.github.com'
TOKEN = os.environ.get('GITHUB_TOKEN') or ''
if not TOKEN:
    print('❌ 缺少 GITHUB_TOKEN'); sys.exit(2)


def api(method, path, payload=None):
    url = API + path
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'token ' + TOKEN,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'User-Agent': 'workbuddy-blog-publisher',
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:400]
        raise RuntimeError('HTTP %s %s %s -> %s' % (e.code, method, path, detail))


def main():
    if len(sys.argv) < 3:
        print('用法: push_via_api.py "提交说明" 文件1 [文件2 ...]'); sys.exit(2)
    message = sys.argv[1]
    files = sys.argv[2:]

    # 1) 远端当前 head
    st, ref = api('GET', '/repos/%s/%s/git/ref/heads/main' % (OWNER, REPO))
    head_sha = ref['object']['sha']
    st, head_commit = api('GET', '/repos/%s/%s/git/commits/%s' % (OWNER, REPO, head_sha))
    base_tree = head_commit['tree']['sha']
    print('远端 head =', head_sha[:10], '| 消息:', head_commit['message'].splitlines()[0][:40])

    # 2) 建 blob
    entries = []
    for f in files:
        raw = open(f, 'rb').read()
        st, blob = api('POST', '/repos/%s/%s/git/blobs' % (OWNER, REPO), {
            'content': base64.b64encode(raw).decode('ascii'),
            'encoding': 'base64',
        })
        entries.append({
            'path': f.replace('\\', '/'),
            'mode': '100644',
            'type': 'blob',
            'sha': blob['sha'],
        })
        print('  blob %-32s %8d B  %s' % (f, len(raw), blob['sha'][:10]))

    # 3) 新 tree（基于远端 tree，覆盖本次文件）
    st, tree = api('POST', '/repos/%s/%s/git/trees' % (OWNER, REPO), {
        'base_tree': base_tree,
        'tree': entries,
    })

    # 4) 新 commit
    st, commit = api('POST', '/repos/%s/%s/git/commits' % (OWNER, REPO), {
        'message': message,
        'tree': tree['sha'],
        'parents': [head_sha],
    })
    print('新 commit =', commit['sha'][:10])

    # 5) 移动分支
    st, upd = api('PATCH', '/repos/%s/%s/git/refs/heads/main' % (OWNER, REPO), {
        'sha': commit['sha'],
        'force': False,
    })
    print('✅ main 已更新 →', upd['object']['sha'][:10])


if __name__ == '__main__':
    main()
