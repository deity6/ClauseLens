# 接口与数据契约 v1

> 前后端、数据、模型代理之间的唯一交接面。改契约必须先改这里，再改代码。

## 1. 标签（Tag）

每个标签有固定 `id`（英文 kebab-case），定义在 `backend/clauselens/taxonomy.py`，同时导出到
`frontend/src/data/taxonomy.json`（由脚本 `scripts/export_taxonomy.py` 生成，前端不手写）。

```jsonc
{
  "id": "data-sold-or-shared",          // 稳定 id
  "polarity": "bad",                      // good | neutral | bad | blocker
  "weight": 8,                            // 1–10，影响评分
  "dimension": "privacy",                 // 见下方维度
  "name_zh": "可能把你的数据给第三方",      // ≤12 字，普通人看得懂
  "name_en": "Data shared with third parties",
  "explain_zh": "条款允许把你的个人信息提供给合作方或广告商。",   // 这对你意味着什么，一句话
  "tosdr_cases": [143, 187],              // 对应的 ToS;DR case id（用于训练/评测映射）
  "keywords_zh": ["..."], "keywords_en": ["..."]  // 规则层种子词（只能看 train 集调）
}
```

维度 `dimension`（雷达图六轴）：
- `privacy` 隐私收集 · `sharing` 数据共享 · `rights` 你的权利（删除/导出/注销）
- `control` 平台单方权力（随时改条款/封号/删内容） · `liability` 责任与争议（免责/仲裁/管辖）
- `content` 你的内容归属（授权范围/版权）

## 2. 分析结果（`/api/analyze` 最终事件 `result`）

```jsonc
{
  "query": {"input": "baidu.com", "mode": "fuzzy", "domain": "baidu.com"},
  "site": {"name": "百度", "domain": "baidu.com", "favicon": "https://..."},
  "jurisdiction": {"code": "CN", "name_zh": "中国大陆", "basis": ["域名 .com + 中文文本 + ICP 备案号"],
                   "laws": ["个人信息保护法", "网络安全法", "民法典 第496条（格式条款）"]},
  "documents": [{"id": "d1", "type": "privacy", "title": "隐私政策", "url": "...", "chars": 32100,
                  "read_minutes": 54, "fetched_at": "ISO8601"}],
  "score": {"value": 42, "grade": "D", "dimensions": {"privacy": 35, "sharing": 30, "rights": 60,
            "control": 40, "liability": 45, "content": 50}},
  "tags": [{"id": "data-sold-or-shared", "confidence": 0.91, "source": "rule|model|rule+model",
            "evidence": [{"doc": "d1", "quote": "我们可能会与合作伙伴共享……", "start": 1203, "end": 1260,
                          "spans": [[3, 12]]}]}],   // v1.1：spans = quote 内规则命中区间，供精确高亮（模型独立命中时为空）
  "compliance": [{"id": "cn-pipl-contact", "law": "个人信息保护法 第17条", "item_zh": "写明个人信息处理者联系方式",
                  "status": "found|missing|unclear",
                  "evidence": {"doc": "d1", "quote": "...", "start": 10, "end": 140, "match_start": 70, "match_end": 80} }],
                  // v1.1：偏移相对 evidence.doc 那份文档（与标签证据一致），quote 保留原文换行
  "tldr": [{"tag": "data-sold-or-shared", "polarity": "bad", "text": "..."}],  // v1.1：结构化，3–5 条，坏在前
  "tldr_zh": ["..."],   // 兼容字段 = tldr[].text
  "stats": {"total_chars": 52000, "read_minutes": 87, "clauses": 412},
  "tosdr": {"id": 870, "rating": "E", "url": "https://tosdr.org/en/service/870"} // 若有社区评级，作为对照
}
```

等级：`A ≥85`、`B ≥70`、`C ≥55`、`D ≥40`、`E <40`；出现 `blocker` 标签时等级上限为 D。

## 3. 流式进度（SSE，`GET /api/analyze?q=...`）

事件按顺序推送，前端等待动画**必须基于这些真实事件推进**：

| event | data | 前端文案示例 |
|---|---|---|
| `stage` | `{"stage":"resolve","message":"..."}` | 正在找到这个网站 |
| `stage` | `{"stage":"discover", "found": 3}` | 翻到了 3 份条款 |
| `document` | `{"title":"隐私政策","chars":32100}` | 这份有 3.2 万字，正常人要读 54 分钟 |
| `stage` | `{"stage":"analyze","progress":0.4}` | 正在逐条阅读… |
| `tag` | `{"id":"...","polarity":"bad"}` | 每发现一个标签就推一次（前端可边找边亮） |
| `result` | 见 §2 | |
| `error` | `{"code":"bad_input|not_found|fetch_failed|blocked|timeout|rate_limited|internal","message_zh":"..."}` | v1.1：限流也以 SSE error 事件返回（HTTP 200） |

阶段名：`resolve → discover → fetch → extract → analyze → score → done`。

## 4. 反馈（`POST /api/feedback`）

```json
{"domain":"baidu.com","tag_id":"data-sold-or-shared","vote":"agree|disagree","comment":"可选 ≤200 字"}
```
存 `data/feedback.jsonl`（不入库）。`GET /api/feedback/summary?domain=` 返回各标签赞同/反对计数。

## 5. 数据集记录（`data/processed/*.jsonl`）

- `segments.jsonl`：`{"domain","doc_type","lang","text","labels":[tag_id...],"case_ids":[...],"source":"tosdr|ota|crawl","url"}`
- `sites.jsonl`：`{"domain","name","tosdr_id","rating","lang","jurisdiction_hint","doc_urls":[...]}`
- `split.json`：`{"seed":42,"train":[domain...],"test":[domain...]}`（按站点划分）

## 变更记录
- v1.1（2026-11-07）：tags.evidence 加 spans；compliance.evidence 改为按文档偏移并带 doc；新增结构化 tldr；限流改为 SSE error 事件；站名优先取 og:site_name。
