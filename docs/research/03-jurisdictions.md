# 03 各法域对网站条款 / 隐私政策的要求对比

> 调研日期：2026-11-07。用途：为 `backend/clauselens/jurisdiction.py` 提供**可在文本中用关键词/规则判断**的必备项检查清单。
> **表述红线**（AGENTS.md §6.7）：检查结果只能是 `found` / `missing` / `unclear`，前端文案写“未在文本中找到 X”，不得写“违法”。很多义务有适用门槛（规模、行业、是否出售数据等），文本层无法判断门槛，所以 `missing` 只表示“没写”，不表示“必须写而没写”。
> 检查项 id 规则：`<法域>-<法律>-<要素>`，要素名尽量与 02 文档的通用要素 id 一致，方便跨法域复用。
> **关键词只是种子**，最终规则/阈值只能在 train 集上调。

## 目录
1. 中国大陆（CN）
2. 欧盟（EU）
3. 美国（US）
4. 英国（UK）
5. 日本（JP）
6. 韩国（KR）
7. 巴西（BR）
8. 印度（IN）
9. 横向对比
10. 如何判定网站属于哪个法域

---

## 1. 中国大陆（CN）

### 1.1 法源
| 法律 | 关键条文 | 来源 |
|---|---|---|
| 《个人信息保护法》（PIPL，2021-11-01 施行） | 7、13–17、23、24、28–31、39、44–50、52、53、57 | https://www.chinalawtranslate.com/%e4%b8%aa%e4%ba%ba%e4%bf%a1%e6%81%af%e4%bf%9d%e6%8a%a4%e6%b3%95/ ；官方库 https://flk.npc.gov.cn/detail?doc=4dfcc01e1c40ad4a4d16efe19a2db14a870f76ae3a722c30e82a12b86e4acdaf |
| 《民法典》合同编 | 496（格式条款提示说明）、497（无效情形）、498（不利解释） | http://www.kmlq.gov.cn/c/2021-11-04/5529663.shtml ，https://www.xbfzb.com/2020-07/29/content_8628962.html |
| 《消费者权益保护法》 | 26（格式条款）、29（收集使用规则） | https://www.chinalawtranslate.com/consumer-protection-law-including-2013-amendments/ |
| 《网络安全法》（2025-10-28 修正，**2026-01-01 施行**，条文序号已变） | 修正后 **第43条**（原第41条：合法正当必要、公开收集使用规则、明示目的方式范围、经同意）、第44条（原42条：不得泄露、未经同意不得提供）、第45条（原43条：删除/更正请求权） | 修正后全文：https://www.cac.gov.cn/2025-12/29/c_1768735112911946.htm ；修正决定：https://www.news.cn/20251029/bc3a57483dbf4b748c9626c0097ff3b4/c.html |
| 《常见类型移动互联网应用程序必要个人信息范围规定》（2021） | 第3条（必要个人信息定义）、第4条（不得因不同意非必要信息而拒绝基本功能）、第5条（39 类 App 清单） | http://www.gov.cn/zhengce/zhengceku/2021-03/23/content_5595088.htm |
| 《App违法违规收集使用个人信息行为认定方法》（2019） | 六类行为 | https://www.cac.gov.cn/2019-12/27/c_1578986455686625.htm |
| GB/T 35273-2020 5.5 | 隐私政策 8 项内容（推荐性国标） | https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=4568F276E0F8346EB0FBA097AA0CE05E |
| 《互联网信息服务管理办法》第12条 | 网站主页显著位置标明经营许可证编号或备案编号（ICP） | https://flk.npc.gov.cn/detail?id=ff8081819c230fa1019c2d0fca0b4b0a |

> 用户提到的 PIPL 第44–50条中，第49条是死者近亲属权利，一般隐私政策可以不写，列为可选项。

### 1.2 必备项检查清单（CN）

| 检查项 id | 法条 | 检查什么（文本规则） | 中文关键词提示 | 英文关键词提示 |
|---|---|---|---|---|
| `cn-pipl-rules-public` | PIPL 7；网安法 43；消保法 29；认定方法 一.1 | 存在独立的隐私政策 / 个人信息保护政策文档，且含“收集/使用”规则段落 | 隐私政策、个人信息保护政策、隐私权政策、个人信息处理规则、收集使用规则 | privacy policy |
| `cn-pipl-contact` | PIPL 17(1)(一) | 写明处理者**名称**（公司全称，匹配“有限公司/股份有限公司”）**且**至少一种联系方式（邮箱/电话/地址正则） | 联系我们、有限公司、注册地址、客服电话、邮箱、个人信息保护负责人 | contact us |
| `cn-pipl-purpose` | PIPL 17(1)(二)、7 | 出现“目的”描述，且与具体信息类型同段出现 | 目的、用于、用途、为了实现 | purpose |
| `cn-pipl-method` | PIPL 17(1)(二) | 写明收集方式（主动提供 / 自动收集 / 第三方获取） | 您主动提供、自动收集、通过第三方获取、方式 | — |
| `cn-pipl-categories` | PIPL 17(1)(二)；认定方法 二.1 | 逐项列出信息种类（检测至少 N 个信息类型词：手机号、位置、设备信息、通讯录…） | 个人信息种类、手机号码、设备信息、位置信息、IMEI、Android ID、MAC | — |
| `cn-pipl-retention` | PIPL 17(1)(二)、19 | 出现保存期限描述（数字+年/月/日，或“最短必要期限”+判断标准） | 保存期限、存储期限、保留期限、最短时间、届满后删除 | retention |
| `cn-pipl-rights-how` | PIPL 17(1)(三)、50 | 写明行使权利的方式和程序（入口路径或申请方式 + 时限） | 行使权利、设置、申请、工作日内、答复、受理 | — |
| `cn-pipl-change-notice` | PIPL 17 第二款、14 第二款 | 写明变更时如何告知；目的/方式/种类变更时重新取得同意 | 本政策更新、变更时、重新取得您的同意、弹窗、推送通知 | — |
| `cn-pipl-separate-consent-sharing` | PIPL 23 | 向其他处理者提供时，告知接收方名称/联系方式/目的/方式/种类 **并**提到“单独同意” | 单独同意、第三方、共享、接收方名称、合作方 | separate consent |
| `cn-pipl-sdk-list` | PIPL 23；认定方法 二.1（含第三方代码、插件） | 存在第三方 SDK 清单（表格或列表，含 SDK 名称、提供方、收集信息、目的） | 第三方SDK、SDK名称、第三方共享清单、合作方清单、接入的第三方 | SDK |
| `cn-pipl-automated-decision` | PIPL 24 | 若出现个性化推荐/定向推送，是否同时提供“不针对个人特征的选项”或便捷拒绝方式 | 个性化推荐、定向推送、关闭个性化、不针对您个人特征 | personalized |
| `cn-pipl-sensitive` | PIPL 28–30 | 若出现敏感信息词，是否说明必要性与影响，并提到单独同意 | 敏感个人信息、生物识别、人脸、身份证、行踪轨迹、金融账户、医疗健康、必要性、单独同意 | sensitive |
| `cn-pipl-minor` | PIPL 31 | 提及不满十四周岁未成年人：监护人同意 + 专门规则 | 不满十四周岁、未成年人、儿童、监护人同意、儿童个人信息保护规则 | children |
| `cn-pipl-cross-border` | PIPL 39 | 若出现境外/出境：告知境外接收方名称、联系方式、目的、方式、种类及向其行使权利的方式，并单独同意 | 境外、出境、跨境、境外接收方、存储于中华人民共和国境内 | cross-border |
| `cn-pipl-right-access-copy` | PIPL 45 | 提到查阅、复制 | 查阅、复制、获取副本 | — |
| `cn-pipl-right-portability` | PIPL 45 第三款 | 提到转移至指定处理者 | 转移、可携带 | — |
| `cn-pipl-right-correct` | PIPL 46 | 提到更正、补充 | 更正、补充、修改个人信息 | — |
| `cn-pipl-right-delete` | PIPL 47 | 提到删除及删除情形 | 删除、主动删除、请求删除 | — |
| `cn-pipl-right-explain` | PIPL 48 | 提到要求解释说明处理规则 | 解释说明 | — |
| `cn-pipl-withdraw` | PIPL 15；认定方法 三.8 | 提到撤回同意及方式 | 撤回同意、撤回授权、关闭权限 | withdraw consent |
| `cn-pipl-no-forced-consent` | PIPL 16；必要信息规定 第4条 | **负面检测**：针对非必要信息出现“不同意则无法使用”类表述 → 标 `unclear` 并给证据 | 如您不同意、将无法使用、无法继续、必须同意 | — |
| `cn-pipl-dpo` | PIPL 52（达到规定数量者） | 提到个人信息保护负责人及联系方式（门槛外可不写，故缺失只作提示） | 个人信息保护负责人、个人信息保护专职部门 | DPO |
| `cn-pipl-local-rep` | PIPL 53（境外处理者） | 境外主体：境内专门机构或代表的名称与联系方式 | 境内代表、境内专门机构 | representative in China |
| `cn-pipl-breach` | PIPL 57 | 承诺发生泄露时通知个人 | 安全事件、泄露、告知您、推送通知 | breach |
| `cn-cac-account-deletion` | 认定方法 六.1–2；网安法 45 | 写明注销账号方式；**负面检测**：注销需邮寄证件/人工审核/冗长等待 | 注销账号、注销账户、账号注销、身份证复印件、人工审核 | delete account |
| `cn-cac-complaint` | 认定方法 六 | 公布投诉、举报方式 | 投诉、举报、反馈渠道 | complaint |
| `cn-cac-zh-hans` | 认定方法 一.4 | 文本为简体中文（语言检测） | — | — |
| `cn-civil-highlight` | 民法典 496；消保法 26① | 服务条款中免责/限制权利条款是否**加粗/下划线/显著提示**（需 HTML 层：`<b>`/`<strong>`/`<u>`/特殊样式占比） | 请您务必审慎阅读、充分理解、加粗、特别提示、重点阅读 | — |
| `cn-civil-no-total-exemption` | 民法典 497(二)(三)；消保法 26② | **负面检测**：不合理免除责任、加重对方责任、限制/排除对方主要权利 | 不承担任何责任、概不负责、一切后果由用户承担、用户不得 | — |
| `cn-civil-no-final-interpretation` | 民法典 498 | **负面检测**：出现“最终解释权” | 最终解释权、解释权归 | — |
| `cn-csl-icp` | 互联网信息服务管理办法 12 | 页面（通常页脚）出现 ICP 备案/许可证号（正则见 §10） | ICP备、ICP证、京ICP备 | — |

---

## 2. 欧盟（EU）

### 2.1 法源
| 法律 | 关键条文 | 来源 |
|---|---|---|
| GDPR（2016/679） | 12（透明）、13（向本人收集时告知）、14（非向本人收集时告知）、7（同意条件）、21（反对权）、22（自动化决策） | https://gdpr-info.eu/art-13-gdpr/ ，https://gdpr-info.eu/art-14-gdpr/ ，https://gdpr-info.eu/art-12-gdpr/ |
| 不公平合同条款指令 93/13/EEC | 第3条（不公平定义）、第5条（清晰易懂、疑义作有利消费者解释）、附录 1(a)–(q) | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:31993L0013 |
| 数字服务法 DSA（2022/2065） | 第14条（条款须写明内容限制、审核政策、算法与人工审核、内部投诉规则；重大变更告知；面向未成年人可理解；超大平台提供简明摘要、多语种） | https://www.eu-digital-services-act.com/Digital_Services_Act_Article_14.html （官方：https://eur-lex.europa.eu/eli/reg/2022/2065/oj ） |
| ePrivacy 指令 2002/58/EC 第5(3)条 | 终端存储（Cookie）需同意 | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32002L0058 |

### 2.2 必备项检查清单（EU）

| 检查项 id | 法条 | 检查什么 | 中文关键词提示 | 英文关键词提示 |
|---|---|---|---|---|
| `eu-gdpr-controller` | GDPR 13(1)(a) | 控制者身份与联系方式；非 EU 主体的欧盟代表 | 数据控制者、联系方式、欧盟代表 | controller, contact details, EU representative, Art. 27 |
| `eu-gdpr-dpo` | GDPR 13(1)(b) | DPO 联系方式（适用时） | 数据保护官 | data protection officer, DPO |
| `eu-gdpr-purpose-basis` | GDPR 13(1)(c) | 目的 **与** 法律依据（同意/合同/法定义务/正当利益…） | 法律依据、合法基础 | purposes, legal basis, lawful basis, Article 6 |
| `eu-gdpr-legit-interest` | GDPR 13(1)(d) | 若依据正当利益，写明具体利益 | 正当利益 | legitimate interests |
| `eu-gdpr-recipients` | GDPR 13(1)(e) | 接收方或接收方类别 | 接收方、第三方类别 | recipients, categories of recipients, processors |
| `eu-gdpr-transfer` | GDPR 13(1)(f) | 第三国传输及充分性决定 / 保障措施（SCC 等） | 向第三国传输、标准合同条款 | third country, adequacy decision, standard contractual clauses, SCC |
| `eu-gdpr-retention` | GDPR 13(2)(a) | 保存期限或确定标准 | 保存期限 | retention period, criteria used to determine |
| `eu-gdpr-rights` | GDPR 13(2)(b) | 访问、更正、删除、限制、反对、可携带 6 项权利 | 访问权、更正、删除、限制处理、反对、可携带 | right of access, rectification, erasure, restriction, object, portability |
| `eu-gdpr-withdraw` | GDPR 13(2)(c)；7(3) | 可随时撤回同意 | 撤回同意 | withdraw consent at any time |
| `eu-gdpr-complaint-sa` | GDPR 13(2)(d) | 向监管机构投诉的权利 | 向监管机构投诉 | lodge a complaint, supervisory authority |
| `eu-gdpr-obligation` | GDPR 13(2)(e) | 提供数据是否为法定/合同要求及不提供的后果 | 是否必须提供、不提供的后果 | statutory or contractual requirement, consequences |
| `eu-gdpr-adm` | GDPR 13(2)(f)；22 | 自动化决策/画像及其逻辑 | 自动化决策、画像 | automated decision-making, profiling, logic involved |
| `eu-gdpr-source` | GDPR 14(1)(d)、14(2)(f) | 非直接收集时：数据类别与来源 | 数据来源 | source, publicly accessible sources, categories of personal data |
| `eu-gdpr-plain-language` | GDPR 12(1) | 可读性指标（句长、术语密度）；儿童友好 | — | concise, transparent, intelligible, plain language |
| `eu-eprivacy-cookie-consent` | ePrivacy 5(3) | Cookie 说明 + 同意/拒绝方式；**负面**：“继续浏览即同意 Cookie” | Cookie、同意、拒绝 | cookies, consent, reject all, by continuing to browse |
| `eu-dsa-moderation` | DSA 14(1) | 条款写明内容限制、审核政策与工具、算法与人工审核、内部投诉 | 内容审核、申诉 | content moderation, algorithmic, human review, complaint-handling |
| `eu-dsa-change-notice` | DSA 14(2) | 重大变更告知 | 重大变更通知 | significant change, notify |
| `eu-dsa-summary` | DSA 14(5)（仅超大平台） | 简明、机器可读的条款摘要 | 摘要 | summary of the terms |
| `eu-uctd-unilateral-change` | 93/13 附录 1(j)(k) | **负面**：无正当理由单方修改 | 随时修改 | modify at any time, sole discretion |
| `eu-uctd-termination` | 93/13 附录 1(f)(g) | **负面**：任意解约 / 无通知终止 | 随时终止 | terminate at any time, without notice |
| `eu-uctd-liability` | 93/13 附录 1(a)(b) | **负面**：排除人身伤害或不当排除责任 | 不承担任何责任 | in no event, not liable |
| `eu-uctd-arbitration-venue` | 93/13 附录 1(q) | **负面**：强制仲裁、限制诉权、远程管辖 | 仲裁、管辖 | arbitration, exclusive jurisdiction, waive |
| `eu-uctd-interpretation` | 93/13 附录 1(m)；第5条 | **负面**：供应方专属解释权 | 最终解释权 | sole right to interpret |
| `eu-uctd-auto-renewal` | 93/13 附录 1(h) | **负面**：自动续期且退出期限过早 | 自动续订 | automatically renew |

---

## 3. 美国（US）

### 3.1 法源
| 法律 | 关键条文 | 来源 |
|---|---|---|
| CCPA/CPRA（加州） | 实施条例 11 CCR §7011 隐私政策必备内容 | https://www.law.cornell.edu/regulations/california/11-CCR-7011 |
| CalOPPA（加州） | Bus. & Prof. Code §22575(b)(1)–(6) | https://california.public.law/codes/business_and_professions_code_section_22575 |
| COPPA（联邦） | 16 CFR §312.4(d) 网站儿童信息告知 | https://www.law.cornell.edu/cfr/text/16/312.4 |
| FTC Act §5 | 不公平/欺骗；FTC 2024 指出“悄悄地、追溯地改隐私政策”可能构成不公平或欺骗 | https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2024/02/ai-other-companies-quietly-changing-your-terms-service-could-be-unfair-or-deceptive |
| 各州综合隐私法 | 弗吉尼亚、科罗拉多、康涅狄格、德州等；条款大同小异（类别、目的、权利、申诉、是否出售/定向广告） | IAPP 追踪器：https://iapp.org/resources/article/us-state-privacy-legislation-tracker/ |

> 美国没有统一联邦隐私法；以下以加州为“最严基线”，其余州的检查项与之基本重合，另加 `us-state-appeal`（多州要求的“拒绝后可申诉”）。各州具体条文本次**未逐一核实**，后续若要做州级细分需补查。

### 3.2 必备项检查清单（US）

| 检查项 id | 法条 | 检查什么 | 中文关键词提示 | 英文关键词提示 |
|---|---|---|---|---|
| `us-ccpa-categories-collected` | §7011(e)(1)(A) | 过去 12 个月收集的个人信息类别（使用法定类别名） | 过去12个月、收集的类别 | categories of personal information, preceding 12 months, identifiers, geolocation, inferences |
| `us-ccpa-sources` | §7011(e)(1)(B) | 来源类别 | 来源 | categories of sources |
| `us-ccpa-purpose` | §7011(e)(1)(C) | 收集的商业目的 | 商业目的 | business or commercial purpose |
| `us-ccpa-sold-shared` | §7011(e)(1)(D)(E)(F) | 是否出售/共享及对象类别；未出售须明说 | 出售、共享 | sell, share, cross-context behavioral advertising, we do not sell |
| `us-ccpa-minors-sale` | §7011(e)(1)(G) | 是否明知出售/共享 16 岁以下信息 | 16岁以下 | under 16 years of age |
| `us-ccpa-disclosed` | §7011(e)(1)(H)–(J) | 为商业目的披露的类别与对象 | 披露 | disclosed for a business purpose |
| `us-ccpa-sensitive` | §7011(e)(1)(K)；(e)(2)(E) | 敏感个人信息是否用于法定外目的；限制使用权 | 敏感个人信息 | sensitive personal information, limit the use |
| `us-ccpa-rights` | §7011(e)(2)(A)–(F) | 知情、删除、更正、opt-out、限制、不受歧视 6 项 | 知情权、删除权、更正、退出、不歧视 | right to know, right to delete, right to correct, opt-out, non-discrimination |
| `us-ccpa-how-to` | §7011(e)(3)(A)(B)(E) | 行使方式、请求表单/门户、核验流程 | 提交请求、核验 | submit a request, verify, toll-free number, webform |
| `us-ccpa-opt-out-link` | §7011(e)(3)(C)；Civ. Code 1798.135 | “Do Not Sell or Share My Personal Information”链接或通知 | 不要出售或共享我的个人信息 | Do Not Sell or Share My Personal Information, Your Privacy Choices |
| `us-ccpa-gpc` | §7011(e)(3)(F)(G) | 如何处理 opt-out 偏好信号（GPC） | 全局隐私控制 | opt-out preference signal, Global Privacy Control, GPC |
| `us-ccpa-agent` | §7011(e)(3)(H) | 授权代理人如何提出请求 | 授权代理人 | authorized agent |
| `us-ccpa-contact` | §7011(e)(3)(J) | 隐私问题联系方式 | 联系方式 | contact, questions or concerns |
| `us-ccpa-updated` | §7011(e)(4) | 最后更新日期 | 更新日期 | last updated, effective date |
| `us-calopa-categories-third` | §22575(b)(1) | 收集的 PII 类别 + 共享第三方类别 | — | categories of personally identifiable information, third-party persons or entities |
| `us-calopa-review-process` | §22575(b)(2) | 若有查看/修改流程须描述 | — | review and request changes |
| `us-calopa-change-process` | §22575(b)(3) | 重大变更如何通知 | 变更通知 | material changes, notify |
| `us-calopa-effective-date` | §22575(b)(4) | 生效日期 | 生效日期 | effective date |
| `us-calopa-dnt` | §22575(b)(5) | 如何响应浏览器 Do Not Track 信号 | 请勿追踪 | Do Not Track, DNT signals |
| `us-calopa-third-party-tracking` | §22575(b)(6) | 是否允许第三方跨站收集 | 第三方跟踪 | third parties may collect, across different websites |
| `us-coppa-operators` | 16 CFR 312.4(d)(1) | 收集儿童信息的运营者姓名、地址、电话、邮箱 | 儿童 | children under 13, operator, COPPA |
| `us-coppa-practices` | 312.4(d)(2) | 收集何种儿童信息、如何使用、披露对象 | 儿童信息 | information we collect from children |
| `us-coppa-parent-rights` | 312.4(d)(5) | 家长可查看/删除/拒绝进一步收集及流程 | 家长 | parent can review, have deleted, refuse further collection |
| `us-ftc-retroactive-change` | FTC Act §5；FTC 2024 | **负面**：条款声称变更可追溯适用于已收集数据、或无通知变更 | 追溯、立即生效 | retroactive, apply to information previously collected, without notice |
| `us-tos-arbitration` | FAA 下通常有效，但属用户关注点 | **负面（用户提示，非合规缺失）**：强制仲裁 + 集体诉讼弃权 | 仲裁、放弃集体诉讼 | binding arbitration, class action waiver, opt out of arbitration within 30 days |
| `us-state-appeal` | 多州综合隐私法（如 VA、CO、CT） | 拒绝权利请求后的申诉流程 | 申诉 | appeal, appeal a decision |

---

## 4. 英国（UK）

### 4.1 法源
| 法律 | 要点 | 来源 |
|---|---|---|
| UK GDPR + DPA 2018 | 告知项与 EU GDPR 第13/14条相同 | https://www.legislation.gov.uk/ukpga/2018/12/contents |
| Data (Use and Access) Act 2025 s103 | 插入 DPA 2018 s164A：**2026-06-19 起**所有控制者须设数据保护投诉流程（可电子提交、30 天内确认收到） | https://www.legislation.gov.uk/ukpga/2025/18/section/103 ；生效日期与要求：https://bratby.law/data-protection-complaints-duaa-controllers-june-2026/ |
| PECR 2003 reg.6 | Cookie 同意（UK 版 ePrivacy） | https://www.legislation.gov.uk/uksi/2003/2426/contents |
| Consumer Rights Act 2015 Part 2 + Schedule 2 | 不公平条款；Schedule 2 灰名单（继承 93/13 附录）；透明与显著要求 | https://www.legislation.gov.uk/ukpga/2015/15/schedule/2 |
| DMCC Act 2024 | 订阅合同规则（续费提醒、易退订），分阶段生效 | https://www.legislation.gov.uk/ukpga/2024/13/contents |

### 4.2 必备项检查清单（UK）
复用 §2 中全部 `eu-gdpr-*` 检查项（改前缀为 `uk-gdpr-*`），监管机构关键词改为 ICO，另加：

| 检查项 id | 法条 | 检查什么 | 中文关键词提示 | 英文关键词提示 |
|---|---|---|---|---|
| `uk-gdpr-ico-complaint` | UK GDPR 13(2)(d) | 提到可向 ICO 投诉 | 信息专员办公室 | Information Commissioner's Office, ICO |
| `uk-dpa-complaint-process` | DPA 2018 s164A（DUAA s103 插入） | 写明向控制者本身投诉的流程/表单 | 投诉流程 | complaint, complaints process, complaint form |
| `uk-gdpr-uk-rep` | UK GDPR 27 | 非英国主体的英国代表 | 英国代表 | UK representative |
| `uk-pecr-cookie` | PECR reg.6 | Cookie 说明 + 同意方式 | Cookie | cookies, consent, PECR |
| `uk-cra-unfair-terms` | CRA 2015 s62 + Sched.2 | **负面**：同 `eu-uctd-*` 各项 | 同上 | 同上 |
| `uk-dmcc-subscription` | DMCC 2024（订阅规则） | 若有订阅：续费提醒、简便退订 | 自动续费、取消订阅 | renewal reminder, cancel subscription |

---

## 5. 日本（JP）— 个人信息保护法（APPI）

### 5.1 法源
- APPI 英文译本（官方）：https://www.japaneselawtranslation.go.jp/en/laws/view/4241/en （本次直接抓取只拿到目录：第32条标题为“Disclosure of Information about the Personal Data a Business Holds”）
- 2022-04-01 修正法与隐私通知的实务要点（森·滨田松本律师事务所，IAPP）：https://iapp.org/news/a/practical-notes-for-the-amended-appi-how-to-amend-privacy-notices
- 要点【文档】：APPI 不直接规定“隐私政策”，而是要求对若干事项“通知 / 公布 / 使本人易于获知”，实务中用隐私政策承载。修正后对“保有个人数据”须可获知：①业者地址与代表人姓名；②更新后的本人权利说明；③保有个人数据的安全管理措施（含在外国处理时的**外国名称**）；利用目的须具体到本人能预见处理方式（如行为分析用于广告需写明）；共同利用须写明管理责任者的地址与代表人；向外国第三方提供须提供该国制度信息。

### 5.2 必备项检查清单（JP）
| 检查项 id | 法条 | 检查什么 | 中文关键词提示 | 英文 / 日文关键词提示 |
|---|---|---|---|---|
| `jp-appi-purpose` | APPI 17、21（利用目的特定与通知/公布） | 具体的利用目的；行为分析时写明分析内容 | 利用目的 | purpose of use / 利用目的 |
| `jp-appi-business-info` | APPI 32 | 业者名称、地址、代表人姓名 | 代表人 | name, address, representative / 名称、住所、代表者 |
| `jp-appi-rights` | APPI 32–35 | 公开（开示）、更正、停止利用/删除的请求程序与费用 | 开示请求 | request for disclosure, correction, cease use / 開示、訂正、利用停止 |
| `jp-appi-security` | APPI 23、32 | 安全管理措施 | 安全管理措施 | security control measures / 安全管理措置 |
| `jp-appi-foreign` | APPI 28；外部环境把握 | 外国名称、外国第三方提供时的该国制度 | 外国 | foreign country / 外国の名称、外的環境の把握 |
| `jp-appi-joint-use` | APPI 27(5)(iii) | 共同利用：项目、范围、目的、管理责任者地址与代表人 | 共同利用 | joint use / 共同利用 |
| `jp-appi-third-party` | APPI 27 | 向第三方提供的条件（原则需同意；opt-out 方式需公布） | 第三方提供 | provision to third parties / 第三者提供 |
| `jp-appi-complaint` | APPI 40 | 投诉窗口 | 投诉窗口 | complaints / 苦情、お問い合わせ窓口 |

---

## 6. 韩国（KR）— 个人信息保护法（PIPA）

### 6.1 法源
- PIPA 英文版（个人信息保护委员会 PDF，2016 修正版）【实测：PDF 第30条】：https://www.privacy.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000827247&fileSn=0 ；最新英文版：https://elaw.klri.re.kr/eng_service/lawView.do?lang=ENG&hseq=53044
- 第30条第1款：隐私政策（个人信息处理方针）应包括 ①处理目的 ②处理与保存期间 ③向第三方提供（如有） ④委托处理（如有） ⑤信息主体及法定代理人的权利义务与行使方法 ⑥隐私负责人（第31条）或负责部门名称、电话等联系方式 ⑦自动收集装置（如 Cookie）的设置、运营与拒绝 ⑧总统令规定的其他事项。第2款：制定/修改时须以易于识别的方式公开。第3款：**隐私政策与合同不一致时，以对信息主体有利者为准**。
- 注：PIPA 2023 年有较大修正，条款序号细节以最新版为准；第30条的核心项未变（本次未逐条核对 2023 修正版）。

### 6.2 必备项检查清单（KR）
| 检查项 id | 法条 | 检查什么 | 中文关键词提示 | 英文 / 韩文关键词提示 |
|---|---|---|---|---|
| `kr-pipa-purpose` | 30(1)1 | 处理目的 | 处理目的 | purpose / 처리 목적 |
| `kr-pipa-retention` | 30(1)2 | 处理与保存期间 | 保存期间 | retention period / 보유기간 |
| `kr-pipa-third-party` | 30(1)3 | 第三方提供（接收方、目的、项目、期间） | 第三方提供 | provision to third party / 제3자 제공 |
| `kr-pipa-consignment` | 30(1)4 | 委托处理（受托方与业务） | 委托处理 | consignment, outsourcing / 처리위탁 |
| `kr-pipa-rights` | 30(1)5 | 权利义务与行使方法（含法定代理人） | 行使方法 | rights and how to exercise / 정보주체의 권리 |
| `kr-pipa-officer` | 30(1)6、31 | 隐私负责人姓名或部门 + 电话 | 隐私负责人 | Chief Privacy Officer / 개인정보 보호책임자 |
| `kr-pipa-cookie` | 30(1)7 | Cookie 等自动收集装置的设置、运营与拒绝方法 | Cookie | cookies, refuse / 쿠키, 자동 수집 장치 |
| `kr-pipa-disclosure` | 30(2) | 政策公开可识别（文档本身存在 + 修订信息） | 修订 | amendment history / 개정 |

---

## 7. 巴西（BR）— LGPD（Lei 13.709/2018）

### 7.1 法源
- 官方文本：https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm （本次访问被拒，未实测）
- 第9条（信息透明权）逐项解读：https://lgpd-brasil.info/capitulo_02/artigo_09 ；检索摘要确认第9条列出：目的特定、处理方式与期限、控制者身份、控制者联系方式、共享使用信息、各处理主体责任、数据主体权利（第18条）。【文档】
- 第41条：须指定 encarregado（DPO），其身份与联系方式须公开、清晰、客观地披露（优先在官网）。【文档，未核原文】
- 第18条：确认处理、访问、更正、匿名化/封锁/删除、可携带、删除基于同意处理的数据、共享对象信息、不同意的后果、撤回同意。【文档】

### 7.2 必备项检查清单（BR）
| 检查项 id | 法条 | 检查什么 | 中文关键词提示 | 英文 / 葡文关键词提示 |
|---|---|---|---|---|
| `br-lgpd-purpose` | 9 I | 具体目的 | 目的 | purpose / finalidade |
| `br-lgpd-form-duration` | 9 II | 处理方式与期限 | 期限 | duration / forma e duração do tratamento |
| `br-lgpd-controller` | 9 III–IV | 控制者身份与联系方式 | 控制者 | controller / controlador, contato |
| `br-lgpd-sharing` | 9 V | 共享使用及目的 | 共享 | shared use / uso compartilhado |
| `br-lgpd-responsibilities` | 9 VI | 处理主体责任 | 责任 | responsibilities / responsabilidades dos agentes |
| `br-lgpd-rights` | 9 VII、18 | 第18条权利清单 | 权利 | rights / direitos do titular |
| `br-lgpd-dpo` | 41 | Encarregado 身份与联系方式 | 数据保护官 | DPO / encarregado |
| `br-lgpd-anpd` | 18 §1 | 可向 ANPD 申诉 | 监管机构 | ANPD, Autoridade Nacional de Proteção de Dados |

---

## 8. 印度（IN）— DPDP Act 2023

### 8.1 法源
- DPDP Act 2023 第5条（通知）【文档，读自法条转载站】：https://www.dpdpa.com/dpdpa2023/chapter-2/section5.html ；官方 PDF：https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf
  - 5(1)：每次请求同意前或同时须告知 (i) 个人数据及处理目的；(ii) 依第6(4)条（撤回同意）和第13条（申诉救济）行使权利的方式；(iii) 向数据保护委员会（Board）投诉的方式。
- **DPDP Rules 2025** 已于 2025 年 11 月公布，**分阶段生效**：先成立 Board，consent manager 注册约 12 个月后，通知形式、安全、泄露通报、留存删除等实体义务再后。规则要求通知用平实语言、逐项列明收集项与目的。来源：https://dpdpaforum.org/bulletin/the-rules-2025-notified 【文档；具体生效日期本次未核】
- 另：第8条要求公布可回答处理问题的联系人（重要数据受托人须有 DPO）；第13条申诉救济。【文档，未核原文条号】

### 8.2 必备项检查清单（IN）
| 检查项 id | 法条 | 检查什么 | 中文关键词提示 | 英文关键词提示 |
|---|---|---|---|---|
| `in-dpdp-data-purpose` | 5(1)(i) | 逐项列明个人数据与目的 | 目的 | personal data, purpose, itemised |
| `in-dpdp-withdraw` | 5(1)(ii)、6(4) | 撤回同意的方式（应与给予同意同样容易） | 撤回同意 | withdraw consent |
| `in-dpdp-grievance` | 5(1)(ii)、13 | 申诉救济方式 | 申诉 | grievance, grievance officer, redressal |
| `in-dpdp-board` | 5(1)(iii) | 向 Data Protection Board of India 投诉的方式 | 数据保护委员会 | Data Protection Board |
| `in-dpdp-contact` | 8 | 可回答问题的联系人 / DPO 联系方式 | 联系人 | contact, Data Protection Officer |
| `in-dpdp-language` | 5(3) | 可选择英文或宪法第八附表所列语言之一 | 语言 | English or any language specified in the Eighth Schedule |

---

## 9. 横向对比（通用要素 × 法域）

✓ = 有明确文本告知要求；○ = 有相关义务但不一定要求写在政策里，或有门槛；— = 未见明确要求（本次调研范围内）。

| 通用要素（02 文档 id） | CN | EU | US(CA) | UK | JP | KR | BR | IN |
|---|---|---|---|---|---|---|---|---|
| identity-contact | ✓ PIPL17 | ✓ 13(1)(a) | ✓ §7011(e)(3)(J) | ✓ | ✓ 32 | ✓ 30(1)6 | ✓ 9 III–IV | ✓ 8 |
| dpo | ○ PIPL52 | ○ 13(1)(b) | — | ○ | — | ✓ 30(1)6 | ✓ 41 | ○ 8 |
| purpose | ✓ | ✓ | ✓ | ✓ | ✓ 21 | ✓ | ✓ | ✓ 5 |
| legal-basis | ○ PIPL13 | ✓ | — | ✓ | — | — | ○ | — |
| data-categories | ✓ | ✓ 14 | ✓ | ✓ | — | ○ | — | ✓ |
| third-party-sharing | ✓ PIPL23（单独同意） | ✓ | ✓ | ✓ | ✓ 27 | ✓ 30(1)3–4 | ✓ 9 V | — |
| sale-or-share / opt-out | — | — | ✓ | — | ○ | — | — | — |
| cross-border | ✓ PIPL39（单独同意） | ✓ | — | ✓ | ✓ 28 | — | ○ | — |
| retention | ✓ | ✓ | ○ | ✓ | — | ✓ | ✓ | — |
| rights | ✓ 44–48 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ 18 | ✓ |
| withdraw-consent | ✓ 15 | ✓ | — | ✓ | — | — | ✓ | ✓ |
| complaint / regulator | ○ 认定方法 | ✓ 13(2)(d) | — | ✓ + s164A | ○ | ✓ | ✓ | ✓ 5(1)(iii) |
| automated-decision | ✓ 24（关闭选项） | ✓ 13(2)(f) | — | ✓ | — | — | — | — |
| children | ✓ 31（<14） | ○ 8 | ✓ COPPA（<13）/<16 | ○ | — | ○ | ○ | ○ |
| cookies | — | ✓ ePrivacy | ✓ CalOPPA DNT / GPC | ✓ PECR | — | ✓ 30(1)7 | — | — |
| changes-notice | ✓ | ○ DSA14(2) | ✓ CalOPPA | ○ | — | ✓ 30(2) | — | — |
| effective-date | — | — | ✓ | — | — | — | — | — |
| account-deletion | ✓ 认定方法 | ○ 删除权 | ○ | ○ | — | — | — | — |
| 不公平格式条款（负面） | ✓ 民法典496–498、消保法26 | ✓ 93/13 | ○ FTC §5 | ✓ CRA2015 | — | ○ 30(3) | — | — |

---

## 10. 如何判定一个网站属于哪个法域（启发式）

### 10.1 原则
- **多标签而非单选**：一个网站可同时落入多个法域（如中国公司的国际站面向欧盟用户 → CN + EU）。PIPL 第3条第2款与 GDPR 第3条第2款都有域外效力：只要“以向境内自然人提供产品或服务为目的”就适用。【PIPL 第3条见 chinalawtranslate 全文；GDPR 第3条 https://gdpr-info.eu/art-3-gdpr/ 】
- 输出契约字段 `jurisdiction.basis[]` 必须列出命中的每条证据（契约 §2 已有此字段），例如 `["ICP 备案号 京ICP证030173号", "简体中文文本", "条款写明适用中华人民共和国法律"]`。
- 置信度按“证据权重求和”，阈值以下显示“无法确定法域，以下按通用要素检查”。

### 10.2 信号与权重（建议初值，需在标注集上校准）

| 信号 | 提取方式 | 指向 | 建议权重 |
|---|---|---|---|
| **条款中的适用法律/管辖条款** | 正则：`适用(中华人民共和国|中国)法律`、`governed by the laws of (the State of )?(\w+)`、`courts of (Ireland|England)` | 对应国家/州 | 高（3） |
| **条款中提到的法规名** | 词表：个人信息保护法 / GDPR, General Data Protection Regulation / CCPA, CPRA, California / UK GDPR, ICO / 個人情報保護法 / 개인정보 보호법 / LGPD / DPDP | 对应法域（可多个） | 高（3） |
| **ICP 备案/许可证号** | 正则：`[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼]ICP(备|证)\s*\d+号(-\d+)?`；公安备案：`[京津沪…]公网安备\s*\d+号` | CN（依据：互联网信息服务管理办法第12条） | 高（3） |
| 监管机构 / 代表 | 词表：网信办、ICO、CNIL、Data Protection Commission (Ireland)、ANPD、PPC、PIPC、Data Protection Board | 对应法域 | 中高（2） |
| 公司注册地址 | 地址正则 + 国名/省市词表（“北京市海淀区…有限公司”、“Dublin 2, Ireland”、“Menlo Park, CA”） | 对应国家 | 中（2） |
| 文本语言 | 语言检测（zh-Hans / zh-Hant / ja / ko / pt-BR / en） | zh-Hans→CN；ja→JP；ko→KR；pt→BR（弱） | 中（1–2）；**en 不指向任何法域** |
| ccTLD | `.cn` `.com.cn` → CN；`.de .fr .ie .eu`… → EU；`.uk` → UK；`.jp` → JP；`.kr` → KR；`.br` → BR；`.in` → IN | 对应国家 | 中（1–2）；`.com/.net/.io` 无指向 |
| 美国特有披露 | “Do Not Sell or Share”、“California residents”、“Your California Privacy Rights”、GPC | US（加州） | 中（2） |
| 欧盟特有披露 | “legal basis”、“supervisory authority”、“Standard Contractual Clauses”、“EU representative” | EU/UK | 中（2） |
| 中国特有披露 | “单独同意”“个人信息保护负责人”“第三方 SDK 清单”“不满十四周岁” | CN | 中（2） |
| 货币/电话格式 | ¥/CNY/人民币、+86/400-；€；£；$ + 美国电话 | 弱指向 | 低（1） |
| `hreflang` / `<html lang>` | HTML 属性 | 语言/地区 | 低（1） |
| 服务器 IP 地理位置 | GeoIP | 托管地 ≠ 法域，CDN 干扰大 | **不建议使用**或权重 0.5 |

### 10.3 判定流程（伪代码）
```
signals = extract(domain, html_footer, documents_text)
scores = defaultdict(float)
for s in signals: scores[s.jurisdiction] += s.weight
selected = [j for j, v in scores.items() if v >= 3]      # 至少一条高权重或多条中权重
if not selected:
    selected = ["GENERIC"]                                  # 仅做 02 文档通用要素检查
# 特殊：多文档时（中国站 + 国际站），按“文档”分别判定，结果按文档挂在 compliance 下
```
### 10.4 易错点
- **`.com` + 中文 + ICP 号**：典型中国站（如 baidu.com），不要因 TLD 判为国际站。
- **繁体中文**：可能是港澳台站点，**不要**直接判 CN；需 ICP 号或“中华人民共和国法律”佐证。
- **全球统一隐私政策**（Google、Meta 等）：同一文本里既有 GDPR 又有 CCPA 章节 → 多法域并行检查；按章节标题（“For users in the EEA”“California”）把检查范围限定到对应段落，避免用加州段落去满足 GDPR 检查项。
- **同一公司分区文档**：服务条款写“若您居住在欧洲经济区，适用附录 X”，`discover.py` 应把附录也抓下来。
- 法域检查结果必须带免责声明：“本检查基于公开文本，不构成法律意见；部分义务有适用门槛。”
