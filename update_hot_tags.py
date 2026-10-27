# -*- coding: utf-8 -*-
"""刷新“全网比价”插件的热门关键词 -> hot_tags.json

用法:
  python update_hot_tags.py                     # 自动模式：抓百度热搜 + 词库匹配 + 当季补位
  python update_hot_tags.py --dry-run           # 只看结果，不写文件
  python update_hot_tags.py --pick "词1,词2,..."  # 人工/AI 指定（推荐由 agent 精选后调用）
  python update_hot_tags.py --list              # 只打印当前热搜榜，供人工挑选

设计要点:
  * 抓取失败 / 候选不足 均 **不覆盖** 现有 hot_tags.json，避免把好数据洗掉
  * 只输出与「购物比价」相关的词，政治/社会新闻类天然被词库过滤掉，不会上图
  * 输出 4~6 个，顺序即前端展示顺序
"""
import io, os, re, sys, json, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'hot_tags.json')
API = 'https://top.baidu.com/api/board?platform=wise&tab=realtime'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0 Safari/537.36')

# ---------- 品牌 / 品类 -> 比价友好的标准商品词 ----------
# 命中顺序从上到下，先品牌后品类
RULES = [
    # 3C 数码
    ('iphone', 'iPhone 17'), ('苹果17', 'iPhone 17'), ('ios 27', 'iPhone 17'),
    ('华为mate', '华为 Mate'), ('mate 80', '华为 Mate'), ('华为mate80', '华为 Mate'),
    ('小米17', '小米 17'), ('redmi', 'Redmi 手机'), ('荣耀', '荣耀手机'),
    ('折叠屏', '折叠屏手机'), ('手机', '智能手机'), ('ipad', 'iPad'),
    ('macbook', 'MacBook'), ('平板', '平板电脑'), ('笔记本', '笔记本电脑'),
    ('airpods', 'AirPods'), ('耳机', '蓝牙耳机'), ('智能手表', '智能手表'),
    ('相机', '相机'), ('大疆', '大疆无人机'), ('无人机', '无人机'),
    ('显卡', '显卡'), ('固态', '固态硬盘'), ('机械键盘', '机械键盘'),
    ('显示器', '显示器'), ('投影', '投影仪'), ('充电宝', '充电宝'),
    ('扫地机', '扫地机器人'), ('机器人', '扫地机器人'),
    # 家电
    ('空气炸锅', '空气炸锅'), ('电饭煲', '电饭煲'), ('破壁机', '破壁机'),
    ('微波炉', '微波炉'), ('洗碗机', '洗碗机'), ('净水器', '净水器'),
    ('加湿器', '加湿器'), ('取暖', '取暖器'), ('电热毯', '电热毯'),
    ('热水器', '热水器'), ('油烟机', '油烟机'), ('空调', '空调'),
    ('冰箱', '冰箱'), ('洗衣机', '洗衣机'), ('电视', '电视'),
    ('吹风机', '吹风机'), ('戴森', '戴森'), ('吸尘器', '吸尘器'),
    # 出行 / 大件
    ('纯电小车', '纯电小车'), ('电动车', '电动车'), ('新能源车', '新能源车'),
    ('汽车', '汽车'), ('电瓶车', '电动车'), ('自行车', '自行车'),
    # 黄金 / 理财类消费
    ('金价', '黄金手镯'), ('黄金', '黄金'), ('金手镯', '黄金手镯'),
    ('金条', '金条'), ('银价', '白银'),
    # 食品生鲜
    ('糖葫芦', '糖葫芦'), ('大闸蟹', '大闸蟹'), ('月饼', '月饼'),
    ('车厘子', '车厘子'), ('榴莲', '榴莲'), ('咖啡', '咖啡'),
    ('奶茶', '奶茶'), ('白酒', '白酒'), ('零食', '零食'),
    ('牛肉', '牛肉'), ('火锅', '火锅'), ('鳗鱼', '鳗鱼'),
    # 服饰 / 美妆 / 母婴 / 宠物
    ('羽绒服', '羽绒服'), ('冲锋衣', '冲锋衣'), ('雪地靴', '雪地靴'),
    ('卫衣', '卫衣'), ('口红', '口红'), ('面膜', '面膜'),
    ('防晒', '防晒霜'), ('精华', '精华液'), ('奶粉', '奶粉'),
    ('尿不湿', '纸尿裤'), ('宠物', '宠物用品'), ('猫粮', '猫粮'),
    ('盲盒', '盲盒'),
]

# ---------- 当季补位（按月份）----------
SEASON = {
    1:  ['羽绒服', '取暖器', '年货礼盒'],
    2:  ['羽绒服', '取暖器', '空气炸锅'],
    3:  ['除湿机', '空气净化器', '春装'],
    4:  ['除湿机', '防晒霜', '吸尘器'],
    5:  ['空调', '风扇', '防晒霜'],
    6:  ['空调', '风扇', '冰箱'],
    7:  ['空调', '冷风扇', '冰箱'],
    8:  ['空调', '电风扇', '旅行箱'],
    9:  ['空气炸锅', '电饭煲', '显示器'],
    10: ['空气炸锅', '取暖器', '加湿器'],
    11: ['取暖器', '加湿器', '羽绒服'],
    12: ['取暖器', '羽绒服', '电热毯'],
}


def fetch_hot():
    req = urllib.request.Request(API, headers={'User-Agent': UA, 'Referer': 'https://top.baidu.com/'})
    raw = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', 'ignore')
    data = json.loads(raw)
    items = data['data']['cards'][0]['content'][0]['content']
    out = []
    for it in items:
        w = (it.get('word') or '').strip()
        if w:
            out.append({'word': w, 'index': it.get('index')})
    return out


def match(hot_list):
    picked, used_kw = [], set()
    for rank, it in enumerate(hot_list):
        w = it['word']
        low = w.lower()
        for key, kw in RULES:
            if key.lower() in low:
                if kw in used_kw:
                    break
                hot = '热搜 #%s' % (it['index'] if it['index'] else '置顶')
                # 给热搜一个简短说明：取热搜词前 12 字
                picked.append({'kw': kw, 'hot': '%s · %s' % (hot, w[:12])})
                used_kw.add(kw)
                break
        if len(picked) >= 4:
            break
    return picked


def fill_season(picked, want=6):
    m = datetime.date.today().month
    have = {p['kw'] for p in picked}
    for kw in SEASON.get(m, []):
        if len(picked) >= want:
            break
        if kw not in have:
            picked.append({'kw': kw, 'hot': '当季热销'})
            have.add(kw)
    return picked


def write_json(picked, source):
    doc = {
        'updated': datetime.date.today().isoformat(),
        'source': source,
        'items': picked,
    }
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print('[ok] 已写入 hot_tags.json：' + ' / '.join(x['kw'] for x in picked))


def main():
    args = sys.argv[1:]
    if '--help' in args or '-h' in args:
        print(__doc__); return

    hot = []
    try:
        hot = fetch_hot()
        print('[ok] 百度热搜 %d 条' % len(hot))
    except Exception as e:
        print('[warn] 热搜抓取失败: %s' % e)

    if '--list' in args:
        for i, it in enumerate(hot):
            print('%3s  %s' % (it['index'] if it['index'] else '顶', it['word']))
        return

    if '--pick' in args:
        idx = args.index('--pick')
        raw = args[idx + 1] if len(args) > idx + 1 else ''
        kws = [x.strip() for x in re.split(r'[,，、|]', raw) if x.strip()]
        if not kws:
            print('[FAIL] --pick 没有解析到关键词'); sys.exit(1)
        picked = [{'kw': k, 'hot': '今日热搜精选'} for k in kws[:8]]
        write_json(picked, '人工/AI 精选')
        return

    if not hot:
        print('[skip] 无热搜数据，保留现有 hot_tags.json 不动'); return

    picked = match(hot)
    print('[ok] 热搜匹配到 %d 个比价词' % len(picked))
    if len(picked) < 4:
        print('[warn] 匹配不足 4 个，用当季词补齐')
    picked = fill_season(picked)

    if '--dry-run' in args:
        print(json.dumps(picked, ensure_ascii=False, indent=2)); return
    write_json(picked, '百度热搜 + 当季热销补位')


if __name__ == '__main__':
    main()
