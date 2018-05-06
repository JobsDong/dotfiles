#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'motong.wyd'

import re
import requests
import chardet
from StringIO import StringIO
from lxml.html.clean import Cleaner
from lxml import html, etree


HEADERS = {"Accept-encoding": "gzip",
           "User-Agent": 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.131'}

TEXT_TAGS = ["p", "br", "hr", "font", "center", "b", "big", "small", "i", "strong", "sub", "sup", "address",
             "blockquote", "cite", "tr", "td", "span"]

CHINA_DOT = [u"。", u"？",u"！",u"，",u"、",u"；",u"：",u"”",u"“",u"’",u"’",u"）",
                 u"（",u"─",u"…",u"—",u"·",u"》",u"《",u"〉",u"〈",
            u".",u"?",u"!",u";",u",",u":",u"-",u"(",u")",u'"']

A_TAG_FLAG = "$#"

DEPTH = 3


def request_url(url, headers=HEADERS):
    # 获取页面内容
    r = requests.get(url, headers=headers)
    html_content = StringIO(r.content).read()

    # 自动解析编码类型
    charset = chardet.detect(html_content)

    # 统一转换UTF8
    return html_content.decode(charset['encoding']).encode("utf-8")


def extract_html(text):
    """
        优化1：根据文本相似性 判断 起始点 : 参看目录1
        优化2：不以HTML标签进行划分，区别对待不同标签，常见文本标签，是不应该分割的：参看目录2
        优化3: 除了使用文本个数分布，应该还有链接个数分布，还同时标点个数分布
    """
    # 将body区域的文本标签去除不分行，保留
    no_text_tag_body_html = replace_text_tag(text)

    # 标记A标签，用于记录Link比率问题
    with_a_no_text_tag_body_html = flag_a_link(no_text_tag_body_html)

    # 转义&置换块状标签做为行节点
    lines = convert_block_lines(html_escape(with_a_no_text_tag_body_html))

    # 计算开始Block和结束Block
    start_block, end_block = count_start_end_block(lines)

    # 文本相似性精确计算开始Line
    start_line = count_start_line(head_title(text), lines, start_block - DEPTH + 1, start_block + DEPTH - 1)

    # 链接数精确计算结束Line
    end_line = count_end_line(lines, max(end_block - DEPTH + 1, 0), min(end_block + DEPTH - 1, len(lines)))

    tmp = []
    for i in xrange(start_line, end_line+1):
        tmp.append(lines[i].replace("$#", "").strip())

    return "".join(tmp)


def count_start_end_block(lines):
    """计算开始Block和结束Block
    """
    # 单词统计表
    block_word_count = []

    # link统计表
    block_link_count = []

    # 标点统计表
    block_flag_count = []

    for i in xrange(len(lines) - DEPTH + 1):
        word_len = sum(count_word_cnt(lines[j]) for j in xrange(i, i+DEPTH))
        link_len = sum(count_link_cnt(lines[j]) for j in xrange(i, i+DEPTH))
        flag_len = sum(count_flag_cnt(lines[j]) for j in xrange(i, i+DEPTH))
        block_word_count.append(word_len)
        block_link_count.append(link_len)
        block_flag_count.append(flag_len)

    # 计算文本
    # 单词数一阶导数
    block_word_der = []
    block_flag_der = []
    block_link_der = []

    for i in xrange(len(lines) - DEPTH):
        block_word_der.append(1.0 * block_word_count[i+1] - block_word_count[i])  # (5/10)
        if block_word_count[i+1] == 0 and block_word_count[i] == 0:
            block_flag_der.append(0.0)
            block_link_der.append(0.0)
        elif block_word_count[i] == 0:
            block_flag_der.append((1.0 * block_flag_count[i + 1] / block_word_count[i + 1]))  # (3/10)
            block_link_der.append((1.0 * block_link_count[i+1]/block_word_count[i+1]))  # (2/10)
        elif block_word_count[i+1] == 0:
            block_flag_der.append(- (block_flag_count[i] / block_word_count[i]))  # (3/10)
            block_link_der.append(- (block_link_count[i]/block_word_count[i]))  # (2/10)
        else:
            block_flag_der.append((1.0 * block_flag_count[i + 1] / block_word_count[i + 1]) - (block_flag_count[i] / block_word_count[i]))  # (3/10)
            block_link_der.append((1.0 * block_link_count[i+1]/block_word_count[i+1]) - (block_link_count[i]/block_word_count[i]))  # (2/10)

    max_word_der, min_word_der, max_flag_der, min_flag_der, max_link_der, min_link_der = max(block_word_der), min(block_word_der), max(block_flag_der), min(block_flag_der), max(block_link_der), min(block_link_der)

    block_word_der = [_count_der(block_word_der[i], max_word_der, min_word_der) for i in xrange(len(lines) - DEPTH)]
    block_flag_der = [_count_der(block_flag_der[i], max_flag_der, min_flag_der) for i in xrange(len(lines) - DEPTH)]
    block_link_der = [_count_der(block_link_der[i], max_link_der, min_link_der) for i in xrange(len(lines) - DEPTH)]

    start_weight_der = -99999.9
    start_der_index = 0
    end_weight_der = 999999.9
    end_der_index = 0
    for i in xrange(len(lines) - DEPTH):
        weight_der = 0.55 * block_word_der[i] + 0.35 * block_flag_der[i] + 0.1 * block_link_der[i]
        if weight_der > start_weight_der:
            start_weight_der = weight_der
            start_der_index = i
        if weight_der < end_weight_der:
            end_weight_der = weight_der
            end_der_index = i

    return start_der_index, end_der_index


def replace_text_tag(html_content):
    """去除文本标签
    """
    # 去除Head等HTML标签
    regex = re.compile(
        r'(?:<!DOCTYPE.*?>)|'  #doctype
        r'(?:<head[\S\s]*?>[\S\s]*?</head>)|'
        r'(?:<!--[\S\s]*?-->)|'  #comment
        r'(?:<script[\S\s]*?>[\S\s]*?</script>)|'  # js...
        r'(?:<style[\S\s]*?>[\S\s]*?</style>)', re.IGNORECASE)  # css
    html_content = regex.sub("", html_content)

    html_content = html_content.decode("utf-8")
    # 清除文本标签
    cleaner = Cleaner(style=True, scripts=True, javascript=True, comments=True,
                      embedded=True, frames=True, remove_tags=TEXT_TAGS, inline_style=True,
                      links=True, meta=True)
    no_text_tag_content = cleaner.clean_html(html_content)
    no_text_tag_content = no_text_tag_content.encode("utf-8")
    return no_text_tag_content.replace("\n", "").replace("\r", "").replace(" ", "")


def convert_block_lines(html_content):
    """
    """
    plain_text = re.sub(r"(?:</?[\s\S]*?>)", '\n', html_content)  # 不包含任何标签的纯html文本
    return [re.sub("\s+", "", line) for line in plain_text.split("\n") if len(line.strip()) != 0]


def flag_a_link(html_content):
    """标记A标签，用于计算link/text问题
    """
    return re.sub(r"<a\s+href[\S]*>|</\s*a>", A_TAG_FLAG, html_content)


def head_title(html_content):
    """使用title中的内容，去匹配标题区域，标题区域大概率是文章开头
    """
    # 获取title
    try:
        tree = html.parse(StringIO(html_content))
        title_content = tree.find(".//title").text
        return title_content
    except:
        return ""


def html_escape(text):
    """
    html转义
    """
    text = (text.replace("&quot;", "\"").replace("&ldquo;", "“").replace("&rdquo;", "”")
            .replace("&middot;", "·").replace("&#8217;", "’").replace("&#8220;", "“")
            .replace("&#8221;", "\”").replace("&#8212;", "——").replace("&hellip;", "…")
            .replace("&#8226;", "·").replace("&#40;", "(").replace("&#41;", ")")
            .replace("&#183;", "·").replace("&amp;", "&").replace("&bull;", "·")
            .replace("&lt;", "<").replace("&#60;", "<").replace("&gt;", ">")
            .replace("&#62;", ">").replace("&nbsp;", " ").replace("&#160;", " ")
            .replace("&tilde;", "~").replace("&mdash;", "—").replace("&copy;", "@")
            .replace("&#169;", "@").replace("♂", "").replace("\r\n|\r", "\n"))
    return text


def count_word_cnt(line):
    """计算单词个数
    """
    return len(line.replace("\n", "").replace(" ", "").replace(A_TAG_FLAG, ""))


def count_link_cnt(line):
    """计算Link个数
    """
    return line.count(A_TAG_FLAG)


def count_flag_cnt(line):
    """计算标点个数
    """
    if isinstance(line, str):
        line = line.decode("utf-8")
    flag_cnt = 0
    for w in line:
        if w in CHINA_DOT:
            flag_cnt += 1

    return flag_cnt


def count_sim(title, line):
    if isinstance(title, str):
        title = title.decode("utf-8")
    if isinstance(line, str):
        line = line.decode("utf-8")
    title = re.sub("\s+", "", title)
    line = re.sub("\s+", "", line)

    # 计算窗口位置 详情参看专利1
    title_2_words = _split_words(title, 2)
    line_2_words = _split_words(line, 2)

    inter_2_set = set(title_2_words).intersection(set(line_2_words))
    union_2_set = set(title_2_words).union(set(line_2_words))

    # 计算窗口位置
    title_3_words = _split_words(title, 3)
    line_3_words = _split_words(line, 3)

    inter_3_set = set(title_3_words).intersection(set(line_3_words))
    union_3_set = set(title_3_words).union(set(line_3_words))

    return (len(inter_2_set)*1.0/len(union_2_set) + len(inter_3_set) * 1.0 / len(union_3_set)) / 2


def _split_words(line, size):
    if isinstance(line, str):
        line = line.decode("utf-8")

    # 计算窗口位置 详情参看专利1
    max_word = None
    max_i = None

    max_pre = 0 # 0是普通，1是空白符，2是标点
    for i, word in enumerate(line):
        if word == u" ":
            pre_n = 1
        elif word in CHINA_DOT:
            pre_n = 2
        else:
            pre_n = 0

        if max_i is None \
         or pre_n > max_pre \
            or (pre_n == max_pre and word >= max_word):
            max_i = i
            max_word = word
            max_pre = pre_n

    max_i = 0 if max_i is None else max_i

    # 窗口大小2
    title_words = []
    for i in xrange(max_i, -1, -size):
        title_words.append(line[max(i-size, 0):i])

    for i in xrange(max_i, len(line), size):
        title_words.append(line[i:min(i+size, len(line))])

    return title_words


def _count_der(der, max_der, min_der):
    if der > 0:
        if max_der == 0:
            return 0.0
        else:
            return der* 1.0 / max_der
    else:
        if min_der == 0:
            return 0.0
        else:
            return der / min_der * -1.0


def count_start_line(title, lines, start, end):
    if len(title.strip()) == 0:
        max_i = 0
        max_len = 0
        for i, line in enumerate(lines):
            if max_len <= count_word_cnt(line):
                max_len = count_word_cnt(line)
                max_i = i
        return max_i
    else:
        max_sim = 0.0
        max_start = 0
        for i in xrange(start, end):
            sim = count_sim(lines[i].replace(A_TAG_FLAG, ""), title.replace(A_TAG_FLAG,""))
            if max_sim <= sim:
                max_sim = sim
                max_start = i

        return max_start


def count_end_line(lines, start, end):
    links = [count_link_cnt(lines[i]) for i in xrange(start, end)]

    link_indexs = [i for i in xrange(start, end) if links[i-start] == min(links)]
    if len(link_indexs) == 1:
        return link_indexs[0]

    flags = [(i, count_flag_cnt(lines[i])) for i in link_indexs]
    flag_indexs = [i[0] for i in flags if i[1] == max([f[1] for f in flags])]
    if len(flag_indexs) == 1:
        return flag_indexs[0]

    words = [(i, count_word_cnt(lines[i])) for i in flag_indexs]
    word_indexs = [i[0] for i in words if i[1] == max([f[1] for f in words])]
    return word_indexs[0][0]


if __name__ == "__main__":
    ## 解析本地文件
    html1 = open("1.html", "rb").read() # http://www.tiku.cn/index/papers/paperdetail?id=1004
    html2 = open("2.html", "rb").read() # http://sports.sina.com.cn/j/2014-05-09/00227155725.shtml
    html3 = open("3.html", "rb").read() # http://sports.qq.com/a/20140509/011085.htm
    print extract_html(html1)
    print "****"
    print extract_html(html2)
    print "****"
    print extract_html(html3)
    print "------"
    # ## 解析网络文件
    html1 = request_url("http://www.tiku.cn/index/papers/paperdetail?id=1004")
    print extract_html(html1)
    print "****"

    # print count_sim("我爱你，真fdaf的", "我很爱你，真fdaf吗")
    # print count_sim("我爱你，真fdaf的", "我爱你 真的")
    #
    # print count_sim("我爱你，真fdaf的", "你fdsf吗，真的假的呀")
    # print count_sim("我爱你，真fdaf的", "你爱我吗，真的假的呀")

    # _split_words("我爱你，真fdaf的", 2) # 我   爱你，  真  fd  af  的
    # _split_words("我很爱你 真fdaf吗", 2) # 我 很爱 你，真f da f吗






