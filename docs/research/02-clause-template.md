# 02 “好的”条款应包含什么：模板定义与霸王条款类型

> 调研日期：2026-11-07。本文件定义 ClauseLens 判断“条款是否完整、是否友好”的**参照模板**。它不是法律意见；产品文案只能说“条款写明 / 未找到”，不得说“违法”。
> 每个要素都标注其规范来源；多个来源交集越大，说明该要素越“基础”。

## 0. 参考来源（一手）

| 简称 | 文件 | URL |
|---|---|---|
| GDPR-13/14 | GDPR 第13条（向本人收集）/ 第14条（非向本人收集）告知项 | https://gdpr-info.eu/art-13-gdpr/ ，https://gdpr-info.eu/art-14-gdpr/ |
| GDPR-12 | GDPR 第12条（简洁、透明、易懂、清晰平实语言） | https://gdpr-info.eu/art-12-gdpr/ |
| GB/T 35273 | GB/T 35273-2020《信息安全技术 个人信息安全规范》5.5 节 + 附录D 隐私政策模板 | https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=4568F276E0F8346EB0FBA097AA0CE05E （全文 PDF 镜像：https://ansafe.xust.edu.cn/DownLoad/2020SafeInstruction.pdf ） |
| TC260 自评估 | TC260-PG-20202A《App收集使用个人信息自评估指南》（2020-07） | https://web.tlawyer.cn/article/a55ba55be50dc595.html （转载；原发布 https://www.tc260.org.cn/ ） |
| 认定方法 | 《App违法违规收集使用个人信息行为认定方法》（2019） | https://www.cac.gov.cn/2019-12/27/c_1578986455686625.htm |
| CCPA §7011 | 加州 CCPA 实施条例 11 CCR §7011（隐私政策内容） | https://www.law.cornell.edu/regulations/california/11-CCR-7011 |
| CalOPPA | 加州 Bus. & Prof. Code §22575 | https://california.public.law/codes/business_and_professions_code_section_22575 |
| FTC | FTC 2012 隐私报告；2024 “悄悄改条款可能构成不公平/欺骗”；2022 暗黑模式报告 | https://www.ftc.gov/news-events/news/press-releases/2012/03/ftc-issues-final-commission-report-protecting-consumer-privacy ，https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2024/02/ai-other-companies-quietly-changing-your-terms-service-could-be-unfair-or-deceptive ，https://www.ftc.gov/system/files/ftc_gov/pdf/P214800+Dark+Patterns+Report+9.14.2022+-+FINAL.pdf |
| 93/13 附录 | 欧盟 93/13/EEC 不公平合同条款指令附录（“可能被视为不公平”的条款灰名单 1(a)–(q)） | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:31993L0013 |
| 民法典 | 民法典第496–498条（格式条款提示说明义务、无效情形、不利解释） | http://www.kmlq.gov.cn/c/2021-11-04/5529663.shtml ，https://www.xbfzb.com/2020-07/29/content_8628962.html |
| 消保法-26 | 消费者权益保护法第26条 | https://www.chinalawtranslate.com/consumer-protection-law-including-2013-amendments/ |

> 关于题目中的“TC260《App隐私政策编写指南》”：本次检索未找到以此为正式标题的 TC260 文件。最接近的权威文件是 **TC260-PG-20202A《App收集使用个人信息自评估指南》**（评估点一 1.5“公开的收集使用规则是否完整”就是在列隐私政策应写什么）以及 **GB/T 35273-2020 附录D《个人信息保护政策模板》**。本文以这两份为准。【未找到原题名文件，已替换】

GB/T 35273-2020 第 5.5 a) 规定隐私政策“内容应包括但不限于”8 项【实测：读 PDF】：①控制者基本情况（身份、联系方式）；②业务功能及各功能收集的信息类型，敏感信息需明确标识；③收集方式、存储期限、数据出境等处理规则；④对外共享/转让/公开披露的目的、信息类型、接收方类型及各自责任；⑤个人信息主体权利和实现机制（查询、更正、删除、注销、撤回同意、获取副本、对自动决策投诉）；⑥提供信息后的安全风险及不提供的影响；⑦安全原则、能力与措施；⑧询问投诉渠道及外部纠纷解决机构。并要求 b) 真实准确完整，c) 清晰易懂、避免歧义，d) 公开且易访问，f) 变化时及时更新并重新告知。附录D 模板目录为：各业务功能的收集使用规则 → 如何保护 → 您的权利 → 如何处理儿童个人信息 → 如何全球范围转移 → 本政策如何更新 → 如何联系我们。

---

## 1. 隐私政策基础要素清单（Privacy Policy Template）

列说明：**来源**用简称；**好写法 / 坏写法**为我们自拟的示例句（非引自任何公司文本），供规则层与标注指南使用。`id` 对应 03 文档中各法域检查项的“通用要素”。

| # | 要素 id | 要素 | 为什么重要 | 来源 | 好的写法 | 坏的写法 |
|---|---|---|---|---|---|---|
| P1 | `identity-contact` | 运营者身份与联系方式（公司全称、地址、邮箱/电话） | 出问题时知道找谁、告谁 | GDPR-13(1)(a)；PIPL 17(1)；GB/T 5.5a1；CCPA §7011(e)(3)(J)；COPPA 312.4(d)(1) | “本政策由××科技有限公司（注册地址：…）提供，个人信息保护事务请联系 privacy@example.com 或 400-xxx。” | “如有疑问请联系我们。”（无任何联系方式） |
| P2 | `dpo` | 个人信息保护负责人 / DPO 联系方式 | 有专人负责，投诉有对口 | GDPR-13(1)(b)；PIPL 52；韩 PIPA 30(1)6 | “我们的个人信息保护负责人可通过 dpo@example.com 联系。” | 未提及 |
| P3 | `data-categories` | 收集的个人信息类型，**按功能逐项列出** | 知道交出了什么 | GDPR-14(1)(d)；PIPL 17(2)；GB/T 5.5a2；认定方法 二.1；CCPA (e)(1)(A) | “注册账号：手机号；下单：收货地址、姓名、电话；定位功能（可选）：精确位置。” | “我们可能收集您的各类信息，包括但不限于……” |
| P4 | `sensitive-marked` | 敏感个人信息单独标识并说明必要性 | 敏感信息泄露危害最大 | PIPL 28–30；GB/T 5.5a2（需明确标识或突出显示） | “**[敏感]** 人脸信息：仅用于实名核验，核验后不保存原始图像。” | 把身份证号、人脸混在普通信息里不加说明 |
| P5 | `purpose` | 每类信息的使用目的 | 目的决定能用到什么程度 | GDPR-13(1)(c)；PIPL 17(2)；CCPA (e)(1)(C) | “收货地址仅用于配送和售后。” | “用于改善服务、提升用户体验及其他商业目的。” |
| P6 | `legal-basis` | 处理的法律依据（同意 / 合同必需 / 法定义务 / 正当利益） | 欧盟法要求；也能看出哪些可拒绝 | GDPR-13(1)(c)(d)；PIPL 13 | “基于您的同意处理位置；基于履行订单合同处理地址。” | 不区分，一律“您同意本政策即视为同意全部处理” |
| P7 | `third-party-sharing` | 向第三方提供：接收方名称/类型、目的、信息种类；第三方 SDK 清单 | 数据流向是最大风险点 | GDPR-13(1)(e)；PIPL 23（单独同意）；GB/T 5.5a4；认定方法 二.1（含第三方代码、插件）；CCPA (e)(1)(D)(E) | 附表：SDK 名称、提供方、收集字段、目的、隐私政策链接 | “我们可能与关联公司及合作伙伴共享您的信息。” |
| P8 | `sale-or-share` | 是否出售/用于跨情境行为广告；opt-out 方式 | 美国法核心；用户最关心 | CCPA (e)(1)(D)、(e)(2)(D)、(e)(3)(C) | “我们过去 12 个月未出售个人信息。如需退出共享，访问‘不要出售或共享我的信息’。” | 不提是否出售 |
| P9 | `cross-border` | 跨境传输：目的地、接收方、保障措施 | 数据出境后保护水平可能下降 | GDPR-13(1)(f)；PIPL 39（单独同意）；GB/T 5.5a3；APPI（外国名称） | “您的信息存储于中国境内；客服数据会传至新加坡的××公司，已签订标准合同。” | “您的信息可能在全球任何地方处理。” |
| P10 | `retention` | 保存期限或确定标准 | 无期限 = 永久留存 | GDPR-13(2)(a)；PIPL 17(2)；GB/T 5.5a3；韩 PIPA 30(1)2 | “订单信息保存 3 年（依电子商务法），注销后 15 个工作日内删除其余信息。” | “在实现目的所需的期间内保存。”（无标准） |
| P11 | `rights` | 用户权利清单：查阅、复制、更正、删除、撤回同意、可携带、限制/拒绝、解释说明 | 权利不写就不知道能行使 | GDPR-13(2)(b)(c)；PIPL 44–48；GB/T 5.5a5；CCPA (e)(2) | 每项权利各写一句 + 入口路径 | “您可以联系我们管理您的信息。” |
| P12 | `rights-how` | 行使权利的方式、时限、身份核验 | 有权利但无路径 = 无权利 | PIPL 17(3)、50；CCPA (e)(3)(A)(B)(E)；DPDP 5(1)(ii) | “设置 › 隐私 › 下载我的数据；15 个工作日内答复。” | 只有一个邮箱，无时限 |
| P13 | `account-deletion` | 注销账号的方式与后果 | 中国治理重点；“注销难”高频投诉 | 认定方法 六.1–2；TC260 6.1；GB/T 5.5a5 | “我的 › 设置 › 注销账号，无需人工审核，7 日冷静期后删除。” | “如需注销请邮寄身份证复印件……”（不合理条件） |
| P14 | `withdraw-consent` | 撤回同意的途径及不影响此前处理 | 同意必须可撤回 | GDPR-13(2)(c)；PIPL 15；认定方法 三.8 | “设置 › 权限管理 可随时关闭；关闭后不影响已提供的服务。” | 未提及撤回 |
| P15 | `automated-decision` | 自动化决策/画像/个性化推荐，及关闭选项 | 防大数据杀熟、信息茧房 | GDPR-13(2)(f)；PIPL 24；认定方法 三.6 | “首页推荐基于浏览记录；可在设置中关闭个性化推荐。” | 有推荐但不提供关闭 |
| P16 | `cookies` | Cookie / 跟踪技术及管理方式；Do Not Track 处理 | 跨站追踪的主要手段 | CalOPPA (b)(5)；韩 PIPA 30(1)7；CCPA (e)(3)(F)（opt-out 偏好信号） | “我们使用分析 Cookie，可在 Cookie 设置中拒绝；我们响应 GPC 信号。” | “继续浏览即视为同意所有 Cookie。” |
| P17 | `children` | 未成年人/儿童信息的处理规则 | 儿童需监护人同意 | PIPL 31（<14 岁专门规则）；COPPA 312.4(d)；GB/T 附录D；CCPA (e)(1)(G)（<16 岁） | “不满 14 周岁需监护人同意；我们制定了《儿童个人信息保护规则》。” | 未提及 |
| P18 | `security` | 安全措施（加密、访问控制、事件响应） | 安全能力的公开承诺 | GB/T 5.5a7；APPI（保有个人数据的安全管理措施） | “传输使用 TLS，敏感字段加密存储，发生泄露将按法律规定通知您。” | “我们采取行业标准措施，但无法保证绝对安全。”（仅此一句） |
| P19 | `breach-notify` | 安全事件告知承诺 | 出事能第一时间知道 | GB/T 5.5a6–7；PIPL 57 | “发生安全事件时，我们将通过站内信/短信告知您影响与建议。” | 未提及 |
| P20 | `complaint` | 投诉渠道 + 外部救济（监管机构、法院） | 内部不处理时能找外部 | GDPR-13(2)(d)；GB/T 5.5a8；认定方法 六；DPDP 5(1)(iii)；英国 DUAA s103 | “对处理结果不满意，可向网信部门投诉或向被告住所地法院起诉。” | 未提及外部救济 |
| P21 | `changes-notice` | 政策变更如何通知、何时生效、是否重新征得同意 | 防“悄悄改条款” | GB/T 5.5f；PIPL 14（目的变更重新同意）、17（变更告知）；CalOPPA (b)(3)；FTC 2024 | “重大变更将提前 15 天弹窗通知并重新征得同意。” | “我们有权随时修改本政策，修改后立即生效，恕不另行通知。” |
| P22 | `effective-date` | 生效/更新日期、历史版本 | 判断是否已过时 | CCPA (e)(4)；CalOPPA (b)(4) | “更新日期：2026-10-01；生效日期：2026-10-15；[历史版本]” | 无日期 |
| P23 | `necessity` | 必要信息与非必要信息区分；拒绝非必要信息不影响基本功能 | 防强制打包授权 | PIPL 16；《必要个人信息范围规定》第4条；认定方法 四.2 | “拒绝开启通讯录权限不影响下单。” | “如您不同意，将无法使用本服务。”（对非必要信息） |
| P24 | `readability` | 简体中文版本、语言平实、可打印/可保存、显著入口 | 看不懂等于没告知 | GDPR-12；PIPL 17（显著方式、清晰易懂）；认定方法 一.3–4、二.4；CCPA (c)(d) | 有摘要、分节标题、表格；入口不超过 4 次点击 | 全文无分段、灰色小字、仅英文 |

---

## 2. 服务条款（ToS）基础要素清单

隐私政策管“数据”，服务条款管“合同权利义务”。好的服务条款应写清以下要素（来源：民法典 496–498、消保法 26、93/13 附录、DSA 第14条、CLAUDETTE 8 类）。

| # | 要素 id | 要素 | 为什么重要 | 来源 | 好的写法 | 坏的写法 |
|---|---|---|---|---|---|---|
| T1 | `parties` | 合同双方：运营主体全称与联系方式 | 知道和谁签约 | 民法典 470（合同一般条款）；消保法；DSA Art.11–12（联络点） | “本协议由您与××（北京）有限公司订立。” | “本平台”“我们”（不写主体） |
| T2 | `highlight-key-terms` | 对免责、限制权利等重大利害条款**加粗/显著提示并可说明** | 未提示的，对方可主张不成为合同内容 | 民法典 496；消保法 26① | “**以下第 8 条限制了我们的责任，请重点阅读。**” | 免责条款混在小字中间 |
| T3 | `service-scope` | 服务内容、收费、自动续费规则 | 防价格与服务单方变动 | 93/13 附录 1(k)(l)；消保法 26 | “会员月费 15 元，到期前 5 天短信提醒，可在设置中关闭自动续费。” | “我们可根据运营需要调整收费标准。” |
| T4 | `changes` | 条款修改：理由、提前通知、用户可拒绝并退出 | 防单方修改 | 93/13 附录 1(j)；DSA 14(2)；FTC 2024 | “重大修改提前 30 天通知，不同意可解约并按比例退费。” | “我们有权随时修改，继续使用即视为接受。” |
| T5 | `termination` | 双方终止权对等，平台终止需理由与通知、可申诉 | 防随意封号 | 93/13 附录 1(f)(g)；DSA 14(1)、20（内部投诉） | “违规封禁会说明理由，您可在 30 日内申诉。” | “我们可在任何时候、以任何理由终止您的账号且不承担责任。” |
| T6 | `content-moderation` | 内容审核规则、算法/人工审核、申诉流程 | 内容被删时知道为何、怎么救 | DSA 14(1)；CLAUDETTE “Content removal” | 列出禁止内容类型、处置方式、申诉入口 | “我们可自行决定删除任何内容。” |
| T7 | `user-content-license` | 用户内容授权：范围、期限、可撤回 | 防“永久、不可撤销、全球、可转授权” | CLAUDETTE；ToS;DR 相关 case | “仅为向您提供服务所需的范围内使用，删除内容后授权终止。” | “您授予我们永久、不可撤销、免费、可转授权的全球许可。” |
| T8 | `liability` | 责任限制合理、不排除人身伤害与故意/重大过失责任 | 防全面免责 | 民法典 497(2)、506；93/13 附录 1(a)(b)；CLAUDETTE “Limitation of liability” | “因我们故意或重大过失造成的损失，我们依法承担责任。” | “在任何情况下我们均不承担任何责任。” |
| T9 | `dispute` | 争议解决：适用法律、管辖法院、是否强制仲裁；保留消费者诉权 | 防异地管辖、强制仲裁 | 93/13 附录 1(q)；CLAUDETTE “Jurisdiction / Choice of law / Arbitration” | “适用中华人民共和国法律，您可向您住所地人民法院起诉。” | “争议提交××仲裁委员会（平台所在地）终局裁决，您放弃集体诉讼权利。” |
| T10 | `interpretation` | 不自设“最终解释权” | 格式条款争议应作不利于提供方的解释 | 民法典 498；93/13 附录 1(m) | 不出现“最终解释权” | “本平台对本协议享有最终解释权。” |
| T11 | `consent-mechanism` | 同意方式：主动勾选、不默认、不“使用即同意” | 未真正知情的同意 | 认定方法 三.4；93/13 附录 1(i)；CLAUDETTE “Contract by using”；GDPR-7 | “请勾选‘我已阅读并同意’（未预先勾选）。” | “访问或使用本网站即表示您同意本条款。” |
| T12 | `minors-summary` | 面向未成年人的服务以其能理解的方式说明；超大平台提供简明摘要 | 可读性是法定义务 | DSA 14(3)(5) | 有“一分钟读懂”摘要 | 无 |
| T13 | `effective-date` | 版本号/生效日期 | 判断适用版本 | 通用 | “版本 5.2，2026-10-15 生效” | 无 |

---

## 3. “霸王条款”常见类型清单

> 用作 `taxonomy.py` 的负面标签候选。“依据”列给出最直接的法律或研究来源；“关键词”只是规则层种子，实际阈值必须在 train 集调（AGENTS.md §5）。
> 极性建议：`bad` = 明显不利；`blocker` = 严重剥夺权利（契约中 blocker 会把等级封顶为 D，需谨慎、只在高置信时给）。

| # | 标签建议 id | 类型 | 典型表述 | 依据 | 极性建议 | 中文关键词提示 | 英文关键词提示 |
|---|---|---|---|---|---|---|---|
| U1 | `terms-change-anytime` | 单方随时修改条款、不通知 | “有权随时修改，恕不另行通知” | 93/13 附录 1(j)；FTC 2024；CLAUDETTE Unilateral change | bad | 随时修改、恕不另行通知、无需通知、继续使用即视为同意修改 | at any time, without notice, sole discretion, continued use constitutes acceptance |
| U2 | `terminate-any-reason` | 单方随意终止/封号 | “可以任何理由终止账号” | 93/13 附录 1(f)(g)；CLAUDETTE Unilateral termination | bad | 有权随时终止、暂停或终止、无需说明理由 | terminate at any time, for any reason, without cause |
| U3 | `liability-disclaimer-total` | 全面免责 | “在任何情况下均不承担任何责任” | 民法典 497(2)；消保法 26②；93/13 附录 1(a)(b)；CLAUDETTE LTD | bad（排除人身伤害时 blocker） | 不承担任何责任、概不负责、免除责任 | in no event shall, not liable for any, disclaim all |
| U4 | `forced-arbitration` | 强制仲裁 | “争议提交××仲裁，终局” | 93/13 附录 1(q)；CLAUDETTE Arbitration | bad | 提交仲裁、仲裁委员会、终局裁决 | binding arbitration, arbitrator, AAA, JAMS |
| U5 | `class-action-waiver` | 放弃集体诉讼 | “您放弃参与集体诉讼的权利” | 93/13 附录 1(q) | blocker | 放弃集体诉讼、代表人诉讼 | class action waiver, waive any right to participate in a class |
| U6 | `venue-provider-home` | 指定平台所在地管辖/外国法 | “由本公司住所地法院管辖” | CLAUDETTE Jurisdiction / Choice of law；民法典 496（重大利害需提示） | bad | 本公司所在地人民法院、住所地法院管辖、适用××州法律 | exclusive jurisdiction, courts of, governed by the laws of |
| U7 | `content-license-perpetual` | 用户内容永久、不可撤销、可转授权 | “永久、不可撤销、全球、免费、可再许可” | CLAUDETTE（内容相关）；ToS;DR case | bad | 永久、不可撤销、全球范围、免费、可转授权、再许可 | perpetual, irrevocable, worldwide, royalty-free, sublicensable |
| U8 | `content-removal-discretion` | 任意删除用户内容 | “可自行决定删除任何内容” | CLAUDETTE Content removal；DSA 14 | bad | 有权删除、自行判断、无需通知删除 | remove any content, at our discretion |
| U9 | `consent-by-use` | 使用即同意 / 浏览即同意 | “访问即表示同意” | CLAUDETTE Contract by using；93/13 附录 1(i) | bad | 使用即视为同意、访问即表示接受、一经注册即视为 | by using, by accessing, you agree |
| U10 | `default-consent` | 默认勾选同意 | 预先勾选“我同意” | 认定方法 三.4；GDPR-7 | bad（通常需页面层检测，文本层弱） | 默认勾选、默认同意 | pre-checked, opt-out by default |
| U11 | `over-collection` | 过度收集 / 捆绑授权 | “不同意则无法使用”（针对非必要信息） | PIPL 16；必要信息范围规定 第4条；认定方法 四 | bad | 包括但不限于、通讯录、不同意将无法使用、一揽子 | including but not limited to, contacts, required to use |
| U12 | `data-sold-or-shared` | 向第三方提供/出售/用于广告 | “与合作伙伴共享” | PIPL 23；CCPA；认定方法 五 | bad | 合作伙伴、关联公司、第三方共享、广告合作 | share with partners, affiliates, sell, advertising partners |
| U13 | `account-deletion-hard` | 注销困难 | 需邮寄证件、人工审核、长期等待 | 认定方法 六.1–2；TC260 6.1 | bad | 注销、身份证复印件、人工审核、不予注销 | delete your account, contact support to close |
| U14 | `retention-indefinite` | 无限期保留 / 注销后仍保留 | “注销后我们仍可保留您的信息” | GDPR-13(2)(a)；PIPL 47 | bad | 永久保存、长期保存、注销后仍保留 | retain indefinitely, even after deletion |
| U15 | `final-interpretation` | “最终解释权” | “本平台享有最终解释权” | 民法典 498；93/13 附录 1(m) | bad | 最终解释权、解释权归 | sole right to interpret, final interpretation |
| U16 | `auto-renew-silent` | 静默自动续费 / 价格单方上调 | “到期自动续费，费用可调整” | 93/13 附录 1(h)(l)；FTC 暗黑模式报告 | bad | 自动续费、自动扣费、价格调整 | automatically renew, auto-renewal, price may change |
| U17 | `no-refund` | 不退款 / 扣留已付款 | “已付费用概不退还” | 93/13 附录 1(d)(f) | bad | 概不退还、不予退款 | non-refundable, no refunds |
| U18 | `assign-without-consent` | 平台可不经同意转让合同 | “我们可将本协议转让给任何第三方” | 93/13 附录 1(p) | neutral/bad | 转让本协议、权利义务转让 | assign this agreement, transfer without consent |
| U19 | `personalized-no-optout` | 个性化推送无关闭选项 / 差别定价 | — | PIPL 24；认定方法 三.6 | bad | 个性化推荐、定向推送、用户画像 | personalized ads, profiling |
| U20 | `sensitive-no-separate-consent` | 敏感信息/对外提供/出境未单独同意 | 一次同意全部 | PIPL 23、29、39 | bad | 单独同意（缺失时）、一并同意 | separate consent, explicit consent |

**对应 93/13 附录灰名单（17 项）**【实测：读 EUR-Lex 原文】：(a) 排除人身伤害责任；(b) 不当排除消费者在不履行时的权利；(c) 消费者受约束而供应方义务取决于其自身意愿；(d) 消费者不履约时扣留已付款；(e) 不成比例的高额违约金；(f) 供应方任意解约；(g) 无合理通知终止无固定期限合同；(h) 自动续期且退出期限过早；(i) 约束消费者接受其订约前无真正机会了解的条款；(j) 无正当理由单方修改条款；(k) 单方修改产品/服务特征；(l) 交付时定价或涨价而无解约权；(m) 由供应方判断是否符合合同或享有专属解释权；(n) 限制供应方对其代理人承诺的责任；(o) 供应方不履约而要求消费者全面履约；(p) 未经同意转让合同降低保障；(q) 排除或阻碍诉权，尤其强制仲裁、限制证据、倒置举证。附录第2段对金融服务和无固定期限合同的 (g)(j)(l) 有例外。

---

## 4. 给后续代理的落地建议

1. **完整性检查（found/missing）**用第1节 P1–P24 + 第2节 T1–T13 的要素 id 作为“通用要素”，再由 03 文档按法域选取子集、挂法条。
2. **负面标签**用第3节 U1–U20 起步，与 ToS;DR case、UNFAIR-ToS 8 类做映射：U1↔Unilateral change，U2↔Unilateral termination，U3↔Limitation of liability，U4↔Arbitration，U6↔Jurisdiction + Choice of law，U8↔Content removal，U9↔Contract by using。
3. **文本层能判 vs 不能判**：U10 默认勾选、P24 入口点击次数、注销是否“真的有效”属于页面/行为层，文本只能判“是否写明”，结果应显示为 `unclear` 而非 `missing`。
4. **极性要保守**：同一句话可能是好的（“我们**不会**出售你的数据”）——规则层必须处理否定词（不会、不得、绝不、never、do not），否则会误伤友好网站（AGENTS.md §5）。
