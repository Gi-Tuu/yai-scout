"""来源可靠性分级（可解释，不装神）。

规则优先：域名后缀 + 已知域名库；未知域名给 T3（行业/一般），并在 tier_reason 写明依据。
LLM 兜底放到验证层迭代，G0 不做。
"""

from __future__ import annotations

from urllib.parse import urlsplit

T1_SUFFIXES = (".gov", ".gov.cn", ".mil", ".edu", ".edu.cn", ".ac.uk", ".int")
T1_DOMAINS = {
    "who.int",
    "un.org",
    "europa.eu",
    "oecd.org",
    "imf.org",
    "worldbank.org",
    "arxiv.org",
    "nist.gov",
    "ietf.org",
    "w3.org",
    "nature.com",
    "science.org",
    "thelancet.com",
    "nejm.org",
    "ieee.org",
    "acm.org",
    # 官方文档/定价页（对本项目的 claim 核验来说属于一手）
    "tavily.com",
    "docs.tavily.com",
    "help.tavily.com",
    "api-docs.deepseek.com",
    "platform.claude.com",
    "docs.anthropic.com",
    "docs.getbifrost.ai",
    "openai.com",
}
T2_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "afp.com",
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "wsj.com",
    "ft.com",
    "economist.com",
    "bloomberg.com",
    "cnbc.com",
    "theguardian.com",
    "xinhuanet.com",
    "people.com.cn",
    "caixin.com",
    "thepaper.cn",
    "36kr.com",
    # 官方代码仓库的 release/license 页面：版本/许可证类 claim 的一手来源
    "github.com",
    # 官方包索引：版本、许可证和包元数据的权威来源
    "pypi.org",
}
T4_DOMAINS = {
    "reddit.com",
    "quora.com",
    "zhihu.com",
    "medium.com",
    "substack.com",
    "blogspot.com",
    "wordpress.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "youtube.com",
    "linkedin.com",
    "tiktok.com",
}


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def classify_source(url: str) -> tuple[int, str]:
    """返回 (tier, 理由)。tier: 1 一手 / 2 权威二手 / 3 一般 / 4 UGC。"""
    host = domain_of(url)
    if not host:
        return 3, "无法解析域名"
    if host.endswith(T1_SUFFIXES):
        return 1, "域名后缀属于政府/学术/国际组织"
    if host in T1_DOMAINS:
        return 1, "已知一手来源域名"
    if host in T2_DOMAINS:
        return 2, "已知权威媒体/通讯社"
    if host in T4_DOMAINS:
        return 4, "用户生成内容/UGC 平台"
    return 3, "未收录域名，默认一般来源"

