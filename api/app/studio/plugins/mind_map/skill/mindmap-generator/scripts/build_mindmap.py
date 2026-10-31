#!/usr/bin/env python3
"""将 Markdown 大纲转换为可交互思维导图 HTML（思维导图生成技能用）。

解析大纲的标题层级（#/##/### 与 - 列表项），组装嵌套数据对象，
注入 assets/mindmap_template.html 模板，输出离线可用的 HTML。

用法：
  python build_mindmap.py <大纲.md> <输出.html> [--title 标题] [--sub 副标题]
"""
import sys
import os
import re
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(SCRIPT_DIR, '..', 'assets', 'mindmap_template.html')

# 主标题与副标题的分隔符（按出现顺序尝试）
SUB_SEPS = ['：', '——', ' :: ', ' | ', ': ']


def split_sub(text):
    for sep in SUB_SEPS:
        if sep in text:
            a, b = text.split(sep, 1)
            if len(a) <= 30:  # 主标题不宜过长
                return a.strip(), b.strip()
    return text.strip(), None


def strip_md(text):
    """去掉常见 Markdown 行内标记（粗体/斜体/行内代码），仅保留纯文字。"""
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    t = re.sub(r'__(.+?)__', r'\1', t)
    t = re.sub(r'\*(.+?)\*', r'\1', t)
    t = re.sub(r'`(.+?)`', r'\1', t)
    return t.strip()


def parse_outline(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.read().splitlines()

    root = {'text': '__root__', 'children': []}
    stack = [(0, root)]
    heading_level = 0   # 最近一次标题层级，列表项/表格行据此确定从属关系
    seen_section = False   # 是否已进入首个二级(##)分章标题
    first_heading = None   # 主根书名节点，用于挂接文末总结性引用块
    skip_depth = 0         # 大纲专属小节（如"内容简介"）的跳过深度，0 表示不跳过
    # 仅存在于大纲、不进入思维导图的标题关键字
    SKIP_MARKERS = ('内容简介',)

    i, n = 0, len(lines)
    while i < n:
        line = lines[i].rstrip()
        stripped = line.strip()
        i += 1
        if not stripped:
            continue

        # 跳过分隔线 / 表格分隔行
        if re.match(r'^[-*_]{3,}\s*$', stripped) or re.match(r'^\|[\s:|-]+\|\s*$', stripped):
            continue
        # 引用块（>）：首个二级分章之前的为文档元信息，跳过；
        # 其后出现的（如文末"一句话总结"）作为总结节点挂到主根下
        if stripped.startswith('>'):
            if not seen_section:
                continue
            text, sub = split_sub(strip_md(stripped.lstrip('>').strip()))
            node = {'text': text}
            if sub:
                node['sub'] = sub
            (first_heading or root).setdefault('children', []).append(node)
            continue

        # 大纲专属小节（如"内容简介"）：仅写入大纲、不进入思维导图
        if skip_depth:
            hm = re.match(r'^(#{1,6})\s+', line)
            if hm and len(hm.group(1)) <= skip_depth:
                skip_depth = 0  # 同层或更浅的标题结束跳过
            else:
                continue  # 跳过该小节的正文/列表

        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            level = len(m.group(1))
            heading_level = level
            if level == 2:
                seen_section = True
            text, sub = split_sub(strip_md(m.group(2).strip()))
            if any(marker in text for marker in SKIP_MARKERS):
                skip_depth = level  # 从此标题起跳过，直到同层或更浅的标题
                continue
        elif re.match(r'^\s*([-*]|\d+[.、])\s+', line):
            # 无序/有序列表项：作为"最近标题"的子节点；同级列表项互为兄弟（而非嵌套）
            # 缩进的列表项（如有序项下的 -）视为更深一层
            indent = len(line) - len(line.lstrip())
            level = heading_level + 1 + indent // 2
            text, sub = split_sub(strip_md(re.sub(r'^\s*([-*]|\d+[.、])\s+', '', line).strip()))
        elif stripped.startswith('|') and stripped.endswith('|'):
            # 表格数据行：第一格为节点文字，第二格为副标题；作为最近标题下的兄弟节点
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            head = cells[0].replace('*', '')
            if len(cells) >= 2 and head and head != '工具':
                node = {'text': strip_md(cells[0]), 'sub': strip_md(cells[1])}
                level = heading_level + 1
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack[-1][1].setdefault('children', []).append(node)
                stack.append((level, node))
            continue
        else:
            # 普通段落行：作为当前栈顶的子节点，避免内容丢失
            level = (stack[-1][0] if stack else 0) + 1
            text, sub = split_sub(strip_md(stripped))

        node = {'text': text}
        if sub:
            node['sub'] = sub
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1]
        parent.setdefault('children', []).append(node)
        stack.append((level, node))
        if first_heading is None:
            first_heading = node

    children = root['children']
    # 单根且带子节点：用该节点作为真正根（避免多出一层"思维导图"壳）
    if len(children) == 1 and children[0].get('children'):
        return children[0]
    return {'text': '思维导图', 'children': children}


def count_nodes(n):
    c = 1
    for k in n.get('children', []):
        c += count_nodes(k)
    return c


def main():
    ap = argparse.ArgumentParser(description="大纲 -> 思维导图 HTML")
    ap.add_argument('outline', help='Markdown 大纲文件')
    ap.add_argument('output', help='输出 HTML 文件')
    ap.add_argument('--title', default=None, help='覆盖根标题')
    ap.add_argument('--sub', default=None, help='根副标题')
    ap.add_argument('--template', default=DEFAULT_TEMPLATE, help='模板 HTML 路径')
    args = ap.parse_args()

    data = parse_outline(args.outline)
    if args.title:
        data['text'] = args.title
    if args.sub:
        data['sub'] = args.sub

    with open(args.template, 'r', encoding='utf-8') as f:
        tpl = f.read()

    # 转义 < 防止破坏 <script>；中文不转义
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    placeholder = 'window.MINDMAP_DATA || {text:"思维导图", sub:"", children:[]}'
    if placeholder not in tpl:
        sys.stderr.write("[错误] 模板占位符不匹配，请检查 mindmap_template.html\n")
        sys.exit(3)
    html = tpl.replace(placeholder, 'window.MINDMAP_DATA || ' + payload)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)
    sys.stderr.write(
        f"思维导图已写出：{args.output}（根=\"{data.get('text')}\"，节点数={count_nodes(data)}）\n"
    )


if __name__ == '__main__':
    main()
