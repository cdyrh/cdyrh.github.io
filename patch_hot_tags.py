# -*- coding: utf-8 -*-
"""给“全网比价”插件的热门关键词加动态加载能力。
- 侧边栏标签改为由同源 hot_tags.json 渲染（失败自动回退默认词）
- sw.js 让 hot_tags.json 走网络优先，避免被 cache-first 长期缓存
可重复执行（幂等）。
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
SW = os.path.join(HERE, 'sw.js')

MARK = 'HOT_TAGS_DYNAMIC_v1'

# ---------- 1. index.html: 标签容器 ----------
html = io.open(INDEX, encoding='utf-8').read()
if MARK in html:
    print('[skip] index.html 已改造过')
else:
    old_tags = re.search(
        r'<div class="pc-tags">\s*(?:<span class="pc-tag"[^>]*>[^<]*</span>\s*)+</div>',
        html)
    if not old_tags:
        print('[FAIL] 找不到 pc-tags 块'); sys.exit(1)
    new_tags = (
        '<div class="pc-tags" id="pc-tags">\n\n'
        '            <!-- %s: 默认词为兜底，运行时由 hot_tags.json 覆盖 -->\n\n'
        "            <span class=\"pc-tag\" onclick=\"quickFill('iPhone 16')\">iPhone 16</span>\n\n"
        "            <span class=\"pc-tag\" onclick=\"quickFill('空气炸锅')\">空气炸锅</span>\n\n"
        "            <span class=\"pc-tag\" onclick=\"quickFill('机械键盘')\">机械键盘</span>\n\n"
        "            <span class=\"pc-tag\" onclick=\"quickFill('蓝牙耳机')\">蓝牙耳机</span>\n\n"
        '          </div>' % MARK)
    html = html[:old_tags.start()] + new_tags + html[old_tags.end():]
    print('[ok] pc-tags 容器已改造')

    # ---------- 2. index.html: 注入渲染 JS ----------
    anchor = 'function quickFill(kw){'
    if anchor not in html:
        print('[FAIL] 找不到 quickFill'); sys.exit(1)
    js = u"""// === 热门关键词动态加载 (%s) ===
// hot_tags.json 由定时任务更新；请求失败 / 超时 / 结构异常时静默保留 HTML 里的默认词。
function pcEsc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function renderHotTags(list){
  var box=document.getElementById('pc-tags');
  if(!box || !list || !list.length) return;
  var html='', n=0;
  list.forEach(function(it){
    var kw = (typeof it==='string') ? it : (it && it.kw);
    if(!kw || n>=8) return;
    var hot = (it && it.hot) ? it.hot : '';
    html += '<span class="pc-tag" title="'+pcEsc(hot? hot+' · 点击立即比价' : '点击立即比价')+'"'
          + " onclick=\\"quickFill('"+pcEsc(kw)+"')\\">"+pcEsc(kw)+'</span>';
    n++;
  });
  if(html) box.innerHTML=html;
}
function loadHotTags(){
  var timer=setTimeout(function(){ timer=null; }, 2500);
  fetch('hot_tags.json?t='+Date.now(), {cache:'no-store'})
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(d){
      if(!timer) return;
      clearTimeout(timer);
      var items = d && (d.items || (d.length ? d : null));
      if(items && items.length) renderHotTags(items);
    })
    .catch(function(){});
}
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded', loadHotTags);
}else{
  loadHotTags();
}

""" % MARK
    html = html.replace(anchor, js + anchor, 1)
    print('[ok] 渲染 JS 已注入')

    io.open(INDEX, 'w', encoding='utf-8', newline='').write(html)
    print('[ok] index.html 已写回')

# ---------- 3. sw.js: hot_tags.json 网络优先 ----------
sw = io.open(SW, encoding='utf-8').read()
if 'hot_tags.json' in sw:
    print('[skip] sw.js 已改造过')
else:
    old = "if (url.pathname === '/version.json' || url.pathname === '/sw.js') return;"
    new = ("if (url.pathname === '/version.json' || url.pathname === '/sw.js'\n"
           "      || url.pathname === '/hot_tags.json') return;")
    if old not in sw:
        print('[WARN] sw.js 未找到版本文件放行行，跳过')
    else:
        sw = sw.replace(old, new, 1)
        io.open(SW, 'w', encoding='utf-8', newline='').write(sw)
        print('[ok] sw.js 已放行 hot_tags.json')
