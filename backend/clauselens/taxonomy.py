"""ClauseLens 标签体系（单一事实来源）。

每个标签：
- id: 稳定英文 id
- polarity: good | neutral | bad | blocker
- weight: 1-10，评分影响力
- dimension: privacy | sharing | rights | control | liability | content
- name_zh / name_en: 普通人看得懂的短名
- explain_zh: 这对你意味着什么
- means_zh: 这条对你的实际影响（一句 15–40 字的人话，显示在「一句话总结」每句下面）
- tosdr: ToS;DR case 标题匹配用的正则（英文，小写匹配）；用于把 ToS;DR 人工标注映射到本标签
- zh / en: 规则层正则（命中句子即候选证据）；只依据领域知识与 train 集调整
- neg_zh / neg_en: 句内出现即否决命中（如"我们不会出售"）

规则正则以句子为单位匹配。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

DIMENSIONS = {
    "privacy": {"name_zh": "隐私收集", "name_en": "Data collection"},
    "sharing": {"name_zh": "数据共享", "name_en": "Data sharing"},
    "rights": {"name_zh": "你的权利", "name_en": "Your rights"},
    "control": {"name_zh": "平台权力", "name_en": "Platform power"},
    "liability": {"name_zh": "责任与纠纷", "name_en": "Liability & disputes"},
    "content": {"name_zh": "内容归属", "name_en": "Your content"},
}


@dataclass
class Tag:
    id: str
    polarity: str
    weight: int
    dimension: str
    name_zh: str
    name_en: str
    explain_zh: str
    means_zh: str
    tosdr: list[str] = field(default_factory=list)
    zh: list[str] = field(default_factory=list)
    en: list[str] = field(default_factory=list)
    neg_zh: list[str] = field(default_factory=list)
    neg_en: list[str] = field(default_factory=list)

    def public(self) -> dict:
        d = asdict(self)
        for k in ("tosdr", "zh", "en", "neg_zh", "neg_en"):
            d.pop(k)
        return d


# 通用否定（句内出现则多数负面标签不成立）
NEG_ZH_COMMON = [r"不会.{0,30}(?:出售|出租|售卖|共享|转让|提供)", r"绝不", r"不得", r"撤回", r"(?:要求|约束)(?:其|第三方|合作方)", r"(?:签署|签订).{0,10}协议", r"统计性数据|匿名化|去标识化",
                 r"第三方(?:软件|平台)?(?:的)?(?:用户)?账号.{0,10}(?:登录|注册)", r"不承担.{0,6}责任", r"(?:权利|义务).{0,10}转让", r"通讯费|信息费"]
NEG_EN_COMMON = [r"\b(?:do|does|will) not (?:sell|rent|share)", r"\bnever (?:sell|rent|share)"]

TAGS: list[Tag] = [
    # ───────────── privacy 隐私收集 ─────────────
    Tag("collects-sensitive", "bad", 7, "privacy", "收集敏感个人信息", "Collects sensitive data",
        "会收集身份证号、人脸、指纹、精确位置、健康等敏感信息，泄露后伤害更大。",
        "身份证、人脸、指纹、精确位置一旦泄露，别人可能冒充你身份或知道你在哪",
        tosdr=[r"biometric", r"sensitive (?:personal )?(?:data|information)", r"health data", r"precise (?:geo)?location"],
        zh=[r"(?:收集|获取|采集|读取|调用|使用|处理|提供|验证|识别|上传|授权).{0,30}(?:身份证|证件号|人脸|面部(?:特征|识别|信息)|指纹|声纹|虹膜|生物识别|精确(?:地理)?位置|地理位置|GPS|行踪轨迹|健康(?:信息|数据|状况)|病历|医疗(?:信息|记录)|宗教信仰|性取向|银行(?:卡号|账号|账户)|支付宝账号)",
            r"(?:身份证|人脸|指纹|声纹|地理位置|GPS|行踪轨迹|银行账号).{0,20}(?:信息)?.{0,10}(?:收集|获取|采集|读取|提供)"],
        neg_zh=[r"是指|指一旦泄露|定义|请勿|勿在|不要|宗教政策|除外|撤回"],
        en=[r"\b(?:biometric|face ?print|fingerprint|precise (?:geo)?location|health (?:data|information)|government[- ]issued id|social security number)"]),
    Tag("collects-contacts-device", "bad", 5, "privacy", "读取通讯录或设备信息", "Reads contacts / device data",
        "可能读取你的通讯录、相册、剪贴板、已安装应用列表或设备标识。",
        "软件可能读你的通讯录、相册、剪贴板、手机型号，用来认出你、也认出你身边的人",
        tosdr=[r"device (?:fingerprint|identifier)", r"address book|contacts", r"installed (?:apps|applications)"],
        zh=[r"(?:通讯录|联系人列表|相册|剪切板|剪贴板|应用(?:安装)?列表|已安装.{0,4}应用|IMEI|MAC\s*地址|IDFA|OAID|Android\s*ID|设备标识)"],
        en=[r"\b(?:address book|contact list|your contacts|clipboard|installed (?:apps|applications)|device identifiers?|IMEI|advertising id|IDFA)\b"]),
    Tag("tracks-across-sites", "bad", 6, "privacy", "跨站追踪你", "Tracks you across sites",
        "使用 Cookie、像素、SDK 等技术在其他网站或应用中追踪你的行为。",
        "你在别的网站搜过什么、买过什么，这边可能也有记录，用来猜你想要什么",
        tosdr=[r"track(?:s|ing)? (?:you|users)? ?(?:on|across) other (?:websites|sites)", r"third[- ]party (?:cookies|trackers)", r"tracking pixels?|web beacons?", r"fingerprint"],
        zh=[r"(?:第三方|合作方).{0,12}(?:Cookie|cookie|SDK|像素|信标|追踪)", r"(?:跨|其他).{0,6}(?:网站|应用|平台).{0,10}(?:追踪|识别|收集)", r"网络信标|像素标签|web\s*beacon"],
        en=[r"\b(?:web beacons?|tracking pixels?|third[- ]party cookies|across (?:other )?(?:websites|sites|apps|services))\b", r"\btrack(?:s|ing)? .{0,30}(?:other|third[- ]party) (?:websites|sites|apps)"]),
    Tag("personalized-ads", "bad", 4, "privacy", "用你的数据推送广告", "Uses your data for ads",
        "会根据你的浏览、购买等行为给你推送个性化广告。",
        "你搜过的、买过的东西会被用来挑广告，用得越久越容易被猜中想看什么",
        tosdr=[r"targeted (?:advertising|ads)", r"personali[sz]ed (?:advertising|ads)", r"used for advertising"],
        zh=[r"(?:个性化|定向|精准|程序化).{0,4}(?:广告|推送|营销|推广)", r"广告(?:的)?(?:投放|推送|推广|触达)", r"(?:推广|营销)信息.{0,10}(?:个性化|推荐|推送)", r"个性化的?第三方推广"],
        neg_zh=[r"拒绝|关闭|退出|不(?:接收|接受)"],
        en=[r"\b(?:targeted|personali[sz]ed|interest[- ]based|behavio(?:u)?ral) (?:advertising|ads)\b"]),
    Tag("collects-beyond-service", "bad", 5, "privacy", "收集范围超出必要", "Collects more than needed",
        "收集的信息超出提供服务所必需的范围，或用于与服务无关的目的。",
        "用「包括但不限于」这类写法，说明以后还能多收别的信息，你未必提前知道",
        tosdr=[r"collects? (?:many|a lot|more) (?:different )?(?:types of )?(?:personal )?(?:data|information)", r"not necessary", r"beyond what is necessary"],
        zh=[r"(?:收集|获取|采集|留存)(?:和使用)?.{0,20}(?:包括但不限于|但不限于).{0,30}(?:信息|数据)", r"(?:我们|平台)(?:还)?(?:可能)?(?:会)?(?:收集|获取).{0,10}(?:其他|更多)(?:相关)?(?:信息|数据)"],
        en=[r"\bincluding,? but not limited to,? .{0,40}(?:information|data)\b"]),
    Tag("data-minimization", "good", 4, "privacy", "只收集必要信息", "Collects only what's needed",
        "明确承诺只收集提供服务所必需的最少信息。",
        "条款说只拿提供服务必需的信息，多余的地址、通讯录它不会要",
        tosdr=[r"minimal (?:data|information)", r"only collects? .{0,20}necessary", r"no (?:personal )?data (?:is )?collected"],
        zh=[r"(?:最少|最小|必要)(?:够用|必要)?(?:原则|范围).{0,10}收集", r"仅(?:会)?收集.{0,20}(?:必要|必需)"],
        en=[r"\b(?:data minimi[sz]ation|only collect .{0,30}(?:necessary|needed))\b"]),
    Tag("no-tracking", "good", 5, "privacy", "不追踪、不做广告画像", "No tracking or ad profiling",
        "明确表示不使用追踪技术或不用于广告。",
        "承诺不做跨站追踪、不拿你的数据打广告，换个网站不会被同一类广告一直跟着",
        tosdr=[r"does not track", r"no (?:third[- ]party )?(?:tracking|trackers|cookies)", r"no (?:targeted )?advertising"],
        zh=[r"(?:不会|不|绝不).{0,6}(?:追踪|跟踪|用于广告|个性化广告|画像)"],
        en=[r"\b(?:do|does|will) not (?:track|use .{0,15}for advertising|serve (?:targeted )?ads)\b"]),

    # ───────────── sharing 数据共享 ─────────────
    Tag("data-sold-or-shared", "bad", 8, "sharing", "可能把你的数据给第三方", "Shares data with third parties",
        "条款允许把你的个人信息提供给合作方、广告商或关联公司。",
        "你的手机号和浏览记录可能被交给合作方、广告商，用来推广告或做用户分析",
        tosdr=[r"(?:personal )?(?:data|information) (?:is|may be) (?:shared|sold|given|transferred)", r"sells? (?:your )?(?:personal )?(?:data|information)", r"shares? .{0,30}(?:third parties|advertisers|partners)", r"affiliates"],
        zh=[r"(?:与|向|给|对).{0,6}(?:第三方|合作伙伴|合作方|关联(?:公司|方)|广告主|第三人).{0,20}(?:共享|提供|披露|转让)", r"(?:共享|提供|披露|转让)给.{0,20}(?:第三方|合作伙伴|合作方|关联(?:公司|方)|广告主|公司)",
            r"(?:将|把)(?:您|你)的.{0,25}(?:提供|共享|披露)给", r"(?:合作方|第三方|第三人|广告主).{0,15}(?:可能)?(?:需要)?(?:使用|获取|接收).{0,10}(?:前述|您的|你的|个人)?信息", r"委托.{0,6}(?:合作方|第三方).{0,6}处理"],
        en=[r"\b(?:share|disclose|sell|provide|transfer)s? .{0,40}(?:with|to) (?:our )?(?:third[- ]part(?:y|ies)|partners|advertisers|affiliates)\b"],
        neg_zh=NEG_ZH_COMMON, neg_en=NEG_EN_COMMON),
    Tag("not-sold", "good", 5, "sharing", "承诺不出售你的数据", "Promises not to sell data",
        "明确写明不会出售或出租你的个人信息。",
        "条款明确说不会出售你的个人信息，号码和浏览习惯不会被打包卖给广告商",
        tosdr=[r"(?:data|information) (?:is )?not (?:being )?sold", r"does not sell", r"not (?:sell|rent|trade)"],
        zh=[r"不会.{0,8}(?:出售|出租|售卖|买卖).{0,6}(?:个人)?信息", r"(?:不|绝不)(?:会)?(?:出售|售卖).{0,8}(?:个人信息|数据)"],
        en=[r"\b(?:do|does|will) not (?:sell|rent|trade) (?:your )?(?:personal )?(?:data|information)\b", r"\bnever (?:sell|rent) "]),
    Tag("cross-border-transfer", "neutral", 4, "sharing", "数据可能传到境外", "Data may leave your country",
        "你的数据可能被传输到其他国家或地区存储和处理，那里的保护水平可能不同。",
        "数据可能存到国外服务器，多数跨国服务都这样，但出问题你维权会更麻烦",
        tosdr=[r"transferred? (?:to|outside) (?:other )?(?:countries|the (?:eu|eea|us))", r"international (?:data )?transfers?"],
        zh=[r"(?:跨境|出境|境外).{0,10}(?:传输|提供|存储|处理)", r"(?:传输|提供|存储).{0,10}(?:境外|中华人民共和国境外|海外)"],
        en=[r"\b(?:transferred?|stored|processed) .{0,30}(?:outside|other countries|internationally)\b", r"\binternational (?:data )?transfers?\b"]),
    Tag("gov-disclosure", "neutral", 3, "sharing", "按要求向政府提供数据", "Discloses data to authorities",
        "在政府、司法机关要求下会提供你的数据（大多数服务都有）。",
        "公安、法院依法来要，它会把你的数据交出去，几乎所有平台都这样，不算额外风险",
        tosdr=[r"law enforcement|government (?:requests|authorities)", r"legal (?:requests|process)"],
        zh=[r"(?:司法|行政|执法|国家)机关.{0,10}(?:要求|依法).{0,10}(?:提供|披露)", r"(?:依法|根据法律).{0,8}(?:提供|披露).{0,10}(?:政府|机关)"],
        en=[r"\b(?:law enforcement|government (?:authorities|agencies|requests)|legal process|subpoena|court order)\b"]),
    Tag("notify-breach", "good", 4, "sharing", "数据泄露会通知你", "Notifies you of breaches",
        "发生数据安全事件时会告知你。",
        "万一数据被偷或泄露，它会主动告诉你，你能及时改密码、盯着有没有人冒用",
        tosdr=[r"notif(?:y|ies|ied) .{0,30}(?:breach|security incident)"],
        zh=[r"(?:安全事件|泄露|泄漏).{0,30}(?:告知|通知|推送)(?:您|你)", r"(?:告知|通知)(?:您|你).{0,20}(?:安全事件|泄露)"],
        en=[r"\bnotify (?:you|users|affected) .{0,40}(?:breach|security incident)\b", r"\b(?:breach|incident) .{0,30}notify\b"]),

    # ───────────── rights 你的权利 ─────────────
    Tag("can-delete-data", "good", 6, "rights", "可以删除你的数据", "You can delete your data",
        "你可以要求删除个人信息。",
        "不想留的信息可以要求它删掉，比如以前发过的帖子、填过的收货地址",
        tosdr=[r"(?:request|can) (?:the )?delet(?:e|ion) (?:of )?(?:your )?(?:personal )?(?:data|information)", r"right to (?:erasure|be forgotten)"],
        zh=[r"(?:请求|要求)(?:我们)?删除", r"删除(?:您的|你的)?(?:个人信息|信息)的(?:请求|申请)", r"(?:您|你)(?:可以|可|有权|能够|也可以|还可以)(?:通过|在|随时)?.{0,30}(?:删除|清除)(?:您的|你的)?.{0,10}(?:信息|记录|数据|内容)",
            r"(?:希望|想要|需要)删除(?:您|你)的.{0,10}(?:个人)?信息"],
        neg_zh=[r"(?:我们|平台|公司|腾讯|阿里巴巴).{0,10}(?:有权|可以|可|将|会).{0,10}删除", r"超出保存期限|保存期限届满|匿名化处理"],
        en=[r"\b(?:request|ask) .{0,20}(?:delet(?:e|ion)|erasure)\b", r"\bright to (?:erasure|deletion|be forgotten)\b"]),
    Tag("can-export-data", "good", 4, "rights", "可以导出你的数据", "You can export your data",
        "你可以获取或导出自己的数据副本。",
        "想要自己发过的内容、记录，可以打包下载一份，换地方用不着从头再来",
        tosdr=[r"(?:retrieve|export|download|copy of) .{0,20}(?:data|information)", r"data portability"],
        zh=[r"(?:获取|导出|下载|复制).{0,10}(?:个人信息)?副本", r"(?:转移|迁移).{0,10}(?:个人信息)"],
        en=[r"\b(?:data portability|export your data|copy of your (?:personal )?(?:data|information)|download your (?:data|information))\b"]),
    Tag("easy-account-deletion", "good", 5, "rights", "可以注销账号", "You can close your account",
        "提供了注销账号的方式。",
        "不想用了在设置里就能注销，不用发邮件、打电话求客服，删了就是删了",
        tosdr=[r"(?:delete|close|deactivate|terminate) (?:your )?account", r"account deletion"],
        zh=[r"注销(?:您|你)?的?(?:账号|账户|帐号)", r"(?:账号|账户|帐号)注销"],
        en=[r"\b(?:delete|close|deactivate) your account\b", r"\baccount deletion\b"]),
    Tag("hard-account-deletion", "bad", 6, "rights", "注销账号很麻烦", "Hard to close account",
        "注销账号条件苛刻或流程繁琐，或注销后数据仍会保留。",
        "想注销要走人工审核、满足一堆条件，号删了数据可能还留着，等于没删干净",
        tosdr=[r"(?:account|data) (?:can ?not|cannot) be (?:fully )?deleted", r"difficult to delete", r"retain(?:s|ed)? .{0,30}after (?:account )?(?:deletion|closure)"],
        zh=[r"注销.{0,30}(?:需满足|应当满足|须满足|以下条件|不可恢复|无法恢复|人工审核)", r"(?:不支持|无法).{0,6}注销"],
        en=[r"\b(?:cannot|can't|unable to) (?:delete|close) (?:your )?account\b", r"\bretain .{0,40}after (?:you )?(?:delete|close|terminat)"]),
    Tag("indefinite-retention", "bad", 5, "rights", "数据保存时间不明确", "Keeps data indefinitely",
        "没有说明保存多久，或在你删除后仍长期保留。",
        "条款没写清楚信息留多久，可能几年后还存在它服务器上，删号也未必清掉",
        tosdr=[r"retain(?:s|ed)? .{0,20}(?:indefinitely|as long as)", r"(?:data|information) (?:is )?kept .{0,20}(?:indefinitely|after)"],
        zh=[r"(?:保存|保留|存储).{0,10}(?:期限|时间)?.{0,10}(?:为实现|实现.{0,6}目的所(?:必需|必要)的(?:最短)?时间|法律法规规定的期限|长期)", r"(?:永久|无限期)(?:保存|保留|存储)"],
        en=[r"\bretain .{0,40}(?:indefinitely|as long as (?:necessary|needed|we deem))\b", r"\bindefinitely\b"]),
    Tag("clear-retention", "good", 3, "rights", "写明了保存多久", "Clear retention period",
        "明确给出了数据保存的具体期限。",
        "写明了数据留几天、几个月还是几年，到期就该删，你能算出旧记录还在不在",
        tosdr=[r"(?:deleted|retained|kept) (?:for|after|within) \d+", r"retention period"],
        zh=[r"(?:保存|保留|存储).{0,10}(?:期限|时间).{0,6}(?:为|不超过)?\s*\d+\s*(?:天|日|个月|月|年)"],
        en=[r"\b(?:retain|keep|store|delete)\w* .{0,30}(?:for|after|within) \d+ (?:days?|months?|years?)\b"]),
    Tag("contact-dpo", "good", 3, "rights", "有个人信息保护联系人", "Privacy contact provided",
        "提供了个人信息保护负责人或隐私问题的联系方式。",
        "有专门管隐私的人或邮箱可以联系，出问题能找到具体的人问，不用只跟机器人绕",
        tosdr=[r"data protection officer|dpo"],
        zh=[r"个人信息保护(?:相关)?(?:负责人|专职部门|专员|机构)", r"(?:隐私|个人信息).{0,10}(?:联系|邮箱|电话).{0,6}(?:@|\d{3,})",
            r"(?:通过|按照|使用).{0,25}联系方式.{0,10}(?:与我们)?(?:联系|反馈)", r"(?:通过|按)以下方式(?:与我们)?联系(?:我们)?", r"联系我们\s*\d*(?:\.\d)*\s*.{0,30}(?:疑问|投诉|建议|问题)",
            r"(?:疑问|问题|投诉|建议).{0,25}(?:通过|请).{0,15}(?:客服|联系方式|方式).{0,6}(?:与我们)?联系"],
        en=[r"\bdata protection officer\b|\bDPO\b", r"\bprivacy@"]),
    Tag("minors-protection", "good", 3, "rights", "专门保护未成年人", "Protects minors",
        "对儿童/未成年人信息有专门的保护规则。",
        "对孩子的信息单独设了更严的规矩，不满十四岁通常要家长同意才能用",
        tosdr=[r"children|minors|under (?:the age of )?1[3-8]", r"coppa"],
        zh=[r"(?:儿童|未成年人|不满(?:十四|14)周岁).{0,20}(?:个人信息|保护|监护人)"],
        en=[r"\b(?:children(?:'s)? (?:privacy|personal information)|under (?:the age of )?1[3-6]|COPPA|parental consent)\b"]),

    # ───────────── control 平台权力 ─────────────
    Tag("terms-change-no-notice", "bad", 8, "control", "可以随时改条款不通知你", "Can change terms without notice",
        "平台可以单方面修改条款，且不一定通知你，继续使用就视为同意。",
        "它想改规则随时能改，改完不用通知你，你接着用就被当作同意新条款",
        tosdr=[r"terms? (?:may|can) be changed? (?:at any time )?without notice", r"without (?:prior )?notice", r"changes? .{0,30}without (?:informing|notif)"],
        zh=[r"(?:有权|随时|单方面?).{0,10}(?:修改|修订|变更|更新).{0,20}(?:协议|条款|规则|政策|内容)", r"(?:修改|修订|变更).{0,30}(?:无需|无须|不另行|不再另行|不必).{0,4}(?:通知|告知)",
            r"(?:无需|无须|不另行|不再另行).{0,4}(?:通知|告知).{0,20}(?:修改|修订|变更)", r"一经.{0,10}(?:公布|发布|公示).{0,10}(?:即|立即)?(?:自动)?生效"],
        neg_zh=[r"(?:会|将)(?:及时|另行|提前|事先)?(?:通过[^。]{0,14})?(?:通知|告知|公告)(?:您|用户)", r"(?:提前|事先|至少提前).{0,8}(?:通知|告知)"],
        en=[r"\b(?:at any time|from time to time).{0,40}(?:modify|change|update|revise)\b", r"\bwithout (?:prior |any )?notice\b", r"\bcontinued use .{0,40}(?:constitutes|deemed|means).{0,20}accept"]),
    Tag("terms-change-notice", "good", 4, "control", "改条款会提前通知你", "Notifies before changing terms",
        "修改条款前会提前通知你，给你时间决定是否继续使用。",
        "条款要改会提前通知你，你有时间看一眼，再决定继续用还是搬走",
        tosdr=[r"(?:notified|notice|informed) (?:in advance|before|prior to) .{0,30}changes?", r"\d+ days?(?:'|’)? (?:prior )?notice"],
        zh=[r"(?:修改|变更|更新).{0,30}(?:提前|事先|\d+\s*(?:日|天)前).{0,10}(?:通知|告知|公示)", r"(?:重大变更|实质性变更).{0,20}(?:弹窗|单独|显著).{0,6}(?:通知|告知|提示)"],
        en=[r"\b(?:\d+|thirty|fourteen|seven) days?(?:'|’)? (?:prior |advance )?notice\b", r"\bnotify you (?:in advance|before|prior)\b"]),
    Tag("account-termination-anytime", "bad", 6, "control", "可以随时封你的号", "Can suspend you anytime",
        "平台可以按自己的判断随时暂停或终止你的账号，理由宽泛。",
        "它觉得你不合适就能封号，理由写得含糊，攒的内容和会员可能一起用不了",
        tosdr=[r"(?:account|service) (?:can|may) be (?:suspended|terminated) .{0,30}(?:any (?:time|reason)|without (?:reason|notice))", r"terminate .{0,20}(?:at any time|for any reason)"],
        zh=[r"(?:有权|可).{0,10}(?:暂停|中止|终止|冻结|封禁|限制).{0,15}(?:账号|账户|帐号|服务)", r"(?:无需|无须|不承担).{0,10}(?:说明理由|任何责任).{0,10}(?:封|终止|暂停)"],
        en=[r"\b(?:suspend|terminate|disable) .{0,30}(?:account|access).{0,30}(?:at any time|for any reason|without (?:notice|reason)|sole discretion)\b"]),
    Tag("content-removal-discretion", "neutral", 3, "control", "可以删除你发布的内容", "Can remove your content",
        "平台可以自行决定删除你发布的内容。",
        "你发的帖子、评论它觉得不合规就能删，不一定会事先问你，多数平台都这么写",
        tosdr=[r"(?:remove|delete) (?:your )?content .{0,30}(?:any (?:time|reason)|discretion)", r"content can be deleted"],
        zh=[r"(?:有权|可|可以|可根据).{0,30}(?:删除|屏蔽|下架|移除|封禁).{0,20}(?:内容|信息|作品|评论|商品|应用|账号)", r"(?:对|将)(?:相应|相关)?(?:信息|内容).{0,6}(?:进行)?(?:删除|屏蔽)"],
        neg_zh=[r"(?:您|你)(?:可以|可|有权).{0,20}删除", r"(?:您|你)的个人信息"],
        en=[r"\b(?:remove|delete|take down) .{0,20}content .{0,30}(?:sole discretion|any reason|at any time)\b"]),
    Tag("default-consent", "bad", 5, "control", "使用即视为同意", "Using it means you agreed",
        "只要你使用服务（或注册、点击）就被视为同意全部条款。",
        "你不点同意也算同意——打开、注册、接着用，就默认接受全部条款",
        tosdr=[r"(?:by|through) (?:using|accessing) .{0,30}(?:agree|accept|consent)", r"browsewrap"],
        zh=[r"(?:一旦|只要|当您|您)?(?:使用|注册|登录|点击|勾选|访问).{0,25}(?:即|就|即视为|视为|即表示|表示).{0,8}(?:同意|接受|认可)"],
        en=[r"\bby (?:using|accessing|registering|clicking).{0,40}(?:you agree|you accept|you consent|constitutes (?:your )?acceptance)\b"]),
    Tag("final-interpretation", "bad", 7, "control", "解释权归平台", "Platform interprets the rules",
        "条款写明由平台对条款作最终解释——条款怎么理解、边界在哪，由平台自己说了算。",
        "条款怎么理解由它说了算，真起争执，它能把模糊的地方往对自己有利的方向解",
        tosdr=[r"final (?:and binding )?interpretation"],
        zh=[r"(?:最终)?解释权.{0,6}(?:归|属于|由).{0,10}(?:本公司|我们|平台|所有)", r"最终解释权"],
        en=[r"\bfinal (?:and binding |binding and final )?interpretation\b",
            r"\binterpretation of (?:these|this|the) (?:terms|agreement)[^.]{0,40}\b(?:is|shall be) (?:final|conclusive|binding)\b",
            r"\b(?:we|company|platform)[^.]{0,30}\breserve[^.]{0,30}\bright to (?:solely )?interpret\b"]),
    Tag("no-automated-access", "neutral", 2, "control", "禁止爬虫和自动访问", "No scraping / bots",
        "禁止使用爬虫、机器人等自动化方式访问服务。",
        "不许用脚本批量抓内容，正常用浏览器看没事，但第三方比价、导出工具可能失灵",
        tosdr=[r"spidering|crawling|automated means|scraping"],
        zh=[r"(?:爬虫|网络机器人|蜘蛛程序|自动化(?:程序|手段|工具|方式)|(?:批量|自动).{0,4}(?:抓取|采集|访问|下载)|抓取(?:本|平台|网站))"],
        en=[r"\b(?:scrap(?:e|ing)|crawl(?:er|ing)|spider(?:ing)?|robots?|automated means)\b"]),

    # ───────────── liability 责任与纠纷 ─────────────
    Tag("broad-liability-waiver", "bad", 7, "liability", "出了问题平台不负责", "Broad liability waiver",
        "大量免除平台的责任——即使服务出错、数据丢失，平台也可能不赔。",
        "号被盗、数据丢了、服务突然停了，它基本上不赔，损失只能你自己消化",
        tosdr=[r"(?:not|no) (?:be )?(?:liable|responsible) for", r"limitation of liability", r"(?:as is|without warranty)"],
        zh=[r"(?:不承担|免除|不负|概不负责|不予赔偿|无需承担|无需负责|不对其|无需因此承担).{0,10}(?:任何)?(?:责任|赔偿|担保|负责)", r"(?:按|以)[\"“「]?现状[\"”」]?(?:提供|为准)",
            r"(?:风险|后果|损失)(?:均)?由(?:您|你|用户)(?:自行)?(?:承担|负担|负责)", r"(?:您|你|用户)(?:将|应)?(?:自行承担|负完全)责任", r"(?:不作|不提供)(?:任何)?.{0,15}(?:保证|担保)",
            r"不(?:应|得)?.{0,12}追究.{0,10}(?:任何)?责任", r"(?:无任何义务|不对).{0,20}(?:承担|负).{0,6}责任", r"亦不对其.{0,6}负责"],
        neg_zh=[r"免除或者?限制.{0,6}责任的条款", r"审慎阅读|仔细阅读|认真阅读"],
        en=[r"\b(?:shall|will) not be (?:liable|responsible) for\b", r"\blimitation of liability\b", r"\bprovided [\"“]?as is[\"”]?"]),
    Tag("liability-cap", "bad", 4, "liability", "赔偿金额有上限", "Capped compensation",
        "即使平台有责任，赔偿也被限制在很低的金额（如你付过的费用）。",
        "就算它真出错，赔偿也有上限，通常就赔你付过的那点会员费",
        tosdr=[r"liability (?:is )?limited to", r"(?:shall not exceed|capped at|maximum (?:aggregate )?liability)"],
        zh=[r"赔偿.{0,20}(?:不超过|以.{0,10}为限|上限)", r"(?:责任|赔偿)(?:总额|金额).{0,10}(?:不超过|限于)"],
        en=[r"\b(?:liability|damages) .{0,40}(?:shall not exceed|limited to|capped at)\b", r"\bin no event .{0,40}exceed\b"]),
    Tag("forced-arbitration", "bad", 7, "liability", "纠纷只能走仲裁", "Forced arbitration",
        "发生纠纷时你不能去法院起诉，只能按平台指定的方式仲裁。",
        "出纠纷不能去法院起诉，得走它指定的仲裁机构，程序更贵更慢，普通人很难撑",
        tosdr=[r"arbitration", r"waive .{0,20}(?:right to|jury)"],
        zh=[r"(?:提交|提请|申请).{0,15}仲裁委员会", r"(?:争议|纠纷).{0,20}(?:仲裁|仲裁解决)"],
        neg_zh=[r"(?:可以|有权|可选择?|均可以?).{0,12}(?:退出|放弃|不参加|拒绝|不接受).{0,8}仲裁"],
        en=[r"\b(?:binding|mandatory|individual) arbitration\b", r"\barbitration (?:agreement|clause)\b"],
        neg_en=[r"\bopt(?:ing)?[ -]?out\b", r"\b(?:may|can) elect not to\b", r"\bright to (?:opt out|decline)\b",
                # "An individual has the possibility … to invoke binding arbitration" 是 DPF 下用户
                # 主动发起仲裁的权利，方向正好相反
                r"\bpossibility\b.{0,60}\b(?:invoke|initiate|seek)\b",
                r"\b(?:you|individual|consumer)s?[^.]{0,50}\b(?:may|can|have the right to)[^.]{0,30}\b"
                r"(?:invoke|initiate|bring|commence)\b"]),
    Tag("class-action-waiver", "bad", 7, "liability", "不能参加集体诉讼", "No class actions",
        "你放弃了和其他用户一起集体起诉平台的权利。",
        "你放弃了和其他用户一起告它的权利，只能一个人去争，几十块的损失不值得打",
        tosdr=[r"class action", r"collective (?:action|lawsuit)"],
        zh=[r"(?:放弃|不得).{0,10}(?:集体诉讼|共同诉讼|代表人诉讼|集团诉讼)"],
        en=[r"\bclass[- ]action\b.{0,40}(?:waive|waiver|not|no)\b", r"\bwaive .{0,30}class\b", r"\bclass action waiver\b"]),
    Tag("far-jurisdiction", "bad", 5, "liability", "打官司要去平台所在地", "Disputes at platform's location",
        "约定纠纷由平台所在地（或境外）法院管辖，你维权成本更高。",
        "真要打官司，得去它公司所在地的法院，跨城甚至出国，路费和律师费先劝退",
        tosdr=[r"(?:jurisdiction|venue) .{0,30}(?:exclusive|courts of)", r"governed by the laws? of"],
        zh=[r"(?:提交|由).{0,15}(?:所在地|住所地).{0,10}(?:人民法院|法院).{0,6}(?:管辖|诉讼)", r"(?:协议签订地|签订地).{0,10}(?:法院|人民法院)"],
        en=[r"\bexclusive (?:jurisdiction|venue)\b", r"\bcourts (?:located )?in .{0,40}(?:exclusive|shall have)\b"]),
    Tag("user-indemnifies", "bad", 4, "liability", "你要替平台赔偿", "You indemnify the platform",
        "如果有人因你的行为起诉平台，你需要承担平台的损失和律师费。",
        "有人因你发的东西告平台，你要赔它的损失和律师费，一条帖子也可能很贵",
        tosdr=[r"indemnif(?:y|ication)", r"defend (?:and )?hold harmless"],
        zh=[r"(?:您|你|用户).{0,10}(?:赔偿|承担).{0,15}(?:我们|平台|本公司|公司).{0,15}(?:损失|费用|律师费)", r"(?:使|保证).{0,6}(?:我们|平台|公司|其)免受",
            r"(?:您|你|用户)(?:同意|应|应当).{0,6}(?:给予|赔偿).{0,30}(?:等额的?赔偿|损失|免受损害|及其)", r"(?:律师费|诉讼费).{0,40}(?:您|你|用户)(?:同意|应)?赔偿"],
        en=[r"\b(?:you (?:agree to |will |shall )?)?indemnif(?:y|ies)\b", r"\bhold (?:us )?harmless\b"]),

    # ───────────── content 内容归属 ─────────────
    Tag("broad-content-license", "bad", 6, "content", "你的内容平台可以随便用", "Broad license to your content",
        "你上传的内容，平台获得免费、永久、可转授权的使用权。",
        "你发的照片、文章，它拿去宣传、做视频、转授权给别人都不用另外付钱",
        tosdr=[r"(?:perpetual|irrevocable|worldwide|royalty[- ]free).{0,40}license", r"license to (?:use|your content)", r"sublicens"],
        zh=[r"(?:免费|无偿)?的?、?(?:永久|不可撤销|全球|非独家|可转授权|可再许可).{0,40}(?:许可|授权|使用权)", r"(?:授予|授权).{0,15}(?:我们|平台|公司).{0,40}(?:永久|不可撤销|全球范围|免费)"],
        en=[r"\b(?:perpetual|irrevocable|worldwide|royalty[- ]free|sublicensable|transferable)\b.{0,60}\blicen[cs]e\b"]),
    Tag("you-own-content", "good", 5, "content", "内容版权归你", "You keep your content",
        "你发布的内容版权仍归你所有。",
        "你发的内容版权仍归你，它只是放在平台上展示，别处要用还得你自己同意",
        tosdr=[r"(?:you|users?) (?:retain|keep|own) .{0,20}(?:rights|ownership|copyright)", r"retains? (?:all )?(?:ownership|rights)"],
        zh=[r"(?:知识产权|著作权|版权).{0,10}(?:归|属于|仍归).{0,6}(?:您|你|用户)"],
        en=[r"\byou (?:retain|keep|own) .{0,30}(?:rights|ownership|copyright|content)\b"]),
    Tag("ai-training", "bad", 5, "content", "可能用你的内容训练 AI", "May train AI on your content",
        "你的内容或数据可能被用于训练人工智能/机器学习模型。",
        "你写的回答、上传的图可能被拿去训练 AI，练出的模型跟你没关系，也拿不回来",
        tosdr=[r"(?:train|training) .{0,20}(?:ai|artificial intelligence|machine learning|models?)"],
        zh=[r"(?:训练|优化).{0,10}(?:模型|算法|人工智能|AI|大模型)", r"(?:机器学习|深度学习|生成式人工智能).{0,20}(?:您的|用户的)?(?:内容|数据|信息)"],
        en=[r"\b(?:train(?:ing)?|improve) .{0,30}(?:machine learning|artificial intelligence|AI|language) models?\b"]),
]

TAG_BY_ID = {t.id: t for t in TAGS}

GRADE_BANDS = [(85, "A"), (70, "B"), (55, "C"), (40, "D"), (0, "E")]


def grade_for(score: float) -> str:
    for lo, g in GRADE_BANDS:
        if score >= lo:
            return g
    return "E"


def public_taxonomy() -> dict:
    return {
        "dimensions": DIMENSIONS,
        "tags": [t.public() for t in TAGS],
        "grades": [{"grade": g, "min": lo} for lo, g in GRADE_BANDS],
    }
