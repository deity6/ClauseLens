"""法域判定 + 必备项检查。

只报告「文本中找到 / 未找到」，不判定违法。检查项依据 docs/research/03-jurisdictions.md。
"""
from __future__ import annotations

import re

CN_TLDS = (".cn", ".com.cn", ".中国")
EU_TLDS = (".de", ".fr", ".it", ".es", ".nl", ".be", ".at", ".se", ".dk", ".fi", ".ie", ".pt", ".pl", ".cz",
           ".gr", ".hu", ".ro", ".sk", ".si", ".bg", ".hr", ".lt", ".lv", ".ee", ".lu", ".mt", ".cy", ".eu")

JURISDICTIONS = {
    "CN": {"name_zh": "中国大陆", "laws": ["个人信息保护法", "网络安全法", "民法典 第496–498条（格式条款）", "消费者权益保护法 第26条"]},
    "EU": {"name_zh": "欧盟", "laws": ["GDPR 通用数据保护条例", "93/13/EEC 不公平合同条款指令", "数字服务法 DSA"]},
    "US": {"name_zh": "美国", "laws": ["CCPA/CPRA（加州）", "COPPA 儿童在线隐私保护法", "CalOPPA"]},
    "UK": {"name_zh": "英国", "laws": ["UK GDPR", "Data Protection Act 2018", "Consumer Rights Act 2015"]},
    "JP": {"name_zh": "日本", "laws": ["个人信息保护法 APPI"]},
    "KR": {"name_zh": "韩国", "laws": ["个人信息保护法 PIPA"]},
    "INTL": {"name_zh": "国际通用", "laws": ["参照 GDPR / OECD 隐私原则"]},
}

# (id, 法条, 检查项, 正则(zh), 正则(en))
CHECKS = {
    "CN": [
        ("cn-pipl-identity", "个人信息保护法 第17条", "写明运营者名称和联系方式",
         r"(?:公司|有限公司|运营者|主体).{0,30}(?:地址|联系|电话|邮箱)|(?:联系我们|联系方式)", None),
        ("cn-pipl-purpose", "个人信息保护法 第17条", "说明收集信息的目的、方式和范围",
         r"(?:收集|使用).{0,20}(?:目的|用途|为了|用于)", None),
        ("cn-pipl-retention", "个人信息保护法 第17、19条", "说明信息保存期限",
         r"(?:保存|保留|存储)(?:期限|时间|期间)", None),
        ("cn-pipl-rights", "个人信息保护法 第44–47条", "告知你查询、复制、更正、删除的方式",
         r"(?:查阅|查询|访问).{0,15}(?:复制|更正|删除)|(?:更正|删除).{0,10}(?:您的)?个人信息", None),
        ("cn-pipl-withdraw", "个人信息保护法 第15条", "说明如何撤回同意",
         r"撤回.{0,6}(?:同意|授权)", None),
        ("cn-pipl-sensitive", "个人信息保护法 第28–30条", "敏感信息单独告知必要性与影响",
         r"敏感个人信息", None),
        ("cn-pipl-third-party", "个人信息保护法 第23条", "向他人提供时告知接收方名称与用途",
         r"(?:第三方|合作方).{0,30}(?:名称|清单|列表|目录)|第三方(?:SDK|共享)(?:清单|列表|目录)", None),
        ("cn-pipl-cross-border", "个人信息保护法 第39条", "如有出境，告知境外接收方情况",
         r"(?:跨境|出境|境外).{0,20}(?:传输|提供|接收方)|(?:境内|中华人民共和国境内).{0,10}(?:存储|储存)", None),
        ("cn-pipl-minors", "个人信息保护法 第31条", "不满14周岁未成年人的保护规则",
         r"(?:不满|未满)?\s*(?:十四|14)\s*周岁|儿童个人信息|未成年人", None),
        ("cn-pipl-account-cancel", "《App违法违规收集使用个人信息行为认定方法》", "提供注销账号的方式",
         r"注销", None),
        ("cn-civil-496", "民法典 第496条", "对免责/限责条款以显著方式提示",
         r"(?:加粗|粗体|下划线|显著(?:方式|标识)|特别提示|请(?:您)?(?:务必)?(?:审慎|仔细|认真)阅读)", None),
        ("cn-pipl-complaint", "个人信息保护法 第50条", "提供投诉、举报渠道",
         r"投诉|举报|申诉", None),
    ],
    "EU": [
        ("eu-gdpr-controller", "GDPR Art.13(1)(a)", "Identity and contact of controller", None,
         r"\b(?:controller|data controller)\b|contact us"),
        ("eu-gdpr-dpo", "GDPR Art.13(1)(b)", "Contact details of the DPO", None, r"data protection officer|\bDPO\b"),
        ("eu-gdpr-legal-basis", "GDPR Art.13(1)(c)", "Legal basis for processing", None,
         r"legal bas[ie]s|legitimate interests?|lawful basis|Art(?:icle)?\.? ?6"),
        ("eu-gdpr-retention", "GDPR Art.13(2)(a)", "Retention period", None, r"retention|retain|how long"),
        ("eu-gdpr-rights", "GDPR Art.13(2)(b)", "Rights of access, rectification, erasure, portability", None,
         r"right (?:of|to) (?:access|rectification|erasure|portability)|rectif"),
        ("eu-gdpr-withdraw", "GDPR Art.13(2)(c)", "Right to withdraw consent", None, r"withdraw (?:your )?consent"),
        ("eu-gdpr-complaint", "GDPR Art.13(2)(d)", "Right to lodge complaint with supervisory authority", None,
         r"supervisory authority|data protection authority|lodge a complaint"),
        ("eu-gdpr-transfer", "GDPR Art.13(1)(f)", "Safeguards for transfers outside EEA", None,
         r"standard contractual clauses|adequacy decision|outside (?:the )?(?:EEA|European)"),
        ("eu-gdpr-automated", "GDPR Art.13(2)(f)", "Automated decision-making / profiling", None,
         r"automated decision|profiling"),
    ],
    "US": [
        ("us-ccpa-categories", "CCPA §1798.100/110", "Categories of personal information collected", None,
         r"categories of personal information"),
        ("us-ccpa-sell-share", "CCPA §1798.120", "Disclose whether data is sold/shared & opt-out", None,
         r"do not sell|opt[- ]out|sell or share|sale of personal information"),
        ("us-ccpa-rights", "CCPA §1798.105/106", "Right to delete / correct / know", None,
         r"right to (?:delete|know|correct)|request (?:to )?delet"),
        ("us-ccpa-nondiscrim", "CCPA §1798.125", "Non-discrimination for exercising rights", None,
         r"discriminat"),
        ("us-coppa", "COPPA", "Children under 13 policy", None, r"under (?:the age of )?13|children|COPPA"),
        ("us-caloppa-dnt", "CalOPPA", "How Do-Not-Track signals are handled", None, r"do not track|DNT|global privacy control"),
        ("us-effective-date", "CalOPPA", "Effective / last updated date", None, r"effective date|last (?:updated|modified|revised)"),
    ],
}
CHECKS["UK"] = [(i.replace("eu-gdpr", "uk-gdpr"), l.replace("GDPR", "UK GDPR"), t, z, e) for i, l, t, z, e in CHECKS["EU"]
                if not i.endswith("transfer")]
CHECKS["INTL"] = CHECKS["EU"]
CHECKS["JP"] = CHECKS["INTL"]
CHECKS["KR"] = CHECKS["INTL"]

ZH_CHECK_FALLBACK = {  # 英文检查项在中文文本中的近似正则（中文站点对外服务时）
    "controller": r"联系我们|联系方式", "dpo": r"个人信息保护负责人|数据保护官",
    "legal-basis": r"法律依据|合法(?:性)?基础|同意|合同履行", "retention": r"保存(?:期限|时间)",
    "rights": r"查阅|更正|删除|可携带|复制", "withdraw": r"撤回", "complaint": r"投诉|监管",
    "transfer": r"跨境|境外", "automated": r"自动化决策|画像",
}


def detect_jurisdiction(domain: str, text: str, zh: bool) -> tuple[str, list[str]]:
    basis = []
    d = domain.lower()
    t = text[:200000]
    if d.endswith(CN_TLDS):
        basis.append(f"域名后缀 {d.rsplit('.', 1)[-1]}")
    if re.search(r"[京沪粤浙苏川闽鄂湘鲁豫冀晋辽吉黑皖赣桂琼渝贵云藏陕甘青宁新蒙津]ICP[备证]\s*\d+", t):
        basis.append("页面含 ICP 备案号")
    if re.search(r"中华人民共和国(?:法律|境内)|个人信息保护法|网络安全法", t):
        basis.append("条款引用中国法律")
    if zh and re.search(r"有限公司|股份有限公司", t):
        basis.append("中文条款 + 中国公司主体")
    if basis:
        return "CN", basis
    if d.endswith(".uk") or re.search(r"\bUK GDPR\b|laws of England", t):
        return "UK", ["英国域名或引用英国法律"]
    if d.endswith(EU_TLDS) or re.search(r"\bGDPR\b|General Data Protection Regulation", t):
        b = ["欧盟成员国域名"] if d.endswith(EU_TLDS) else ["条款引用 GDPR"]
        if not d.endswith(EU_TLDS) and re.search(r"\bCCPA\b|California Consumer Privacy Act|laws of the State of", t):
            return "US", ["条款引用美国州法（同时引用 GDPR）"]
        return "EU", b
    if re.search(r"\bCCPA\b|\bCPRA\b|California|laws of the State of|United States", t):
        return "US", ["条款引用美国法律"]
    if d.endswith(".jp"):
        return "JP", ["日本域名"]
    if d.endswith(".kr"):
        return "KR", ["韩国域名"]
    if zh:
        return "CN", ["中文条款（推测）"]
    return "INTL", ["未能确定所属地区，按国际通用要求检查"]


def check(jur: str, texts: dict[str, str] | str, zh: bool) -> list[dict]:
    """texts: {doc_id: 正文}。证据偏移相对于所在文档（与标签证据一致）。"""
    if isinstance(texts, str):
        texts = {"d1": texts}
    out = []
    for cid, law, item, rz, re_en in CHECKS.get(jur, CHECKS["INTL"]):
        pat = rz if zh and rz else re_en
        if zh and not rz:
            key = cid.split("-", 2)[-1]
            pat = ZH_CHECK_FALLBACK.get(key, re_en)
        if not zh and not re_en:
            pat = rz
        ev = None
        if pat:
            for did, text in texts.items():
                m = re.search(pat, text, re.I)
                if m:
                    a = max(0, m.start() - 60)
                    b = min(len(text), m.end() + 60)
                    ev = {"doc": did, "quote": text[a:b], "start": a, "end": b,
                          "match_start": m.start(), "match_end": m.end()}
                    break
        out.append({"id": cid, "law": law, "item_zh": _zh_item(item), "status": "found" if ev else "missing", "evidence": ev})
    return out


_EN2ZH = {
    "Identity and contact of controller": "写明运营者身份和联系方式",
    "Contact details of the DPO": "提供数据保护官（DPO）联系方式",
    "Legal basis for processing": "说明处理数据的法律依据",
    "Retention period": "说明数据保存期限",
    "Rights of access, rectification, erasure, portability": "告知你访问、更正、删除、导出数据的权利",
    "Right to withdraw consent": "告知你可以撤回同意",
    "Right to lodge complaint with supervisory authority": "告知你可以向监管机构投诉",
    "Safeguards for transfers outside EEA": "数据出欧盟时的保障措施",
    "Automated decision-making / profiling": "说明是否有自动化决策/画像",
    "Categories of personal information collected": "列出收集的个人信息类别",
    "Disclose whether data is sold/shared & opt-out": "说明是否出售数据，并提供拒绝方式",
    "Right to delete / correct / know": "告知你删除、更正、知情的权利",
    "Non-discrimination for exercising rights": "承诺不因你行使权利而区别对待",
    "Children under 13 policy": "13 岁以下儿童保护规则",
    "How Do-Not-Track signals are handled": "说明如何处理「请勿追踪」信号",
    "Effective / last updated date": "写明生效/更新日期",
}


def _zh_item(item: str) -> str:
    return _EN2ZH.get(item, item)
