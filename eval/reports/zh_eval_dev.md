# 中文规则层评测（dev）

## A. CAPP-130 主题级（57 个 App，19327 句）

| 主题 | P | R | F1 | 支持 |
|---|---|---|---|---|
| 共享、委托、转让、公开（披露） | 0.585 | 0.133 | 0.217 | 2276 |
| 特殊人群 | 0.614 | 0.599 | 0.606 | 716 |
| 联系方式 | 0.274 | 0.157 | 0.199 | 370 |
| 数据、权限管理 | 0.728 | 0.156 | 0.257 | 2554 |
| 存储方式 | 0.779 | 0.102 | 0.18 | 657 |
| 隐私政策的授权、修改与变更 | 0.972 | 0.137 | 0.24 | 503 |
| 权限获取 | 0.218 | 0.233 | 0.225 | 940 |

## B. 细标签银标集（400 句）

micro P 0.772 / R 0.772 / F1 0.772

| 标签 | P | R | F1 | 支持 | 误报 |
|---|---|---|---|---|---|
| broad-liability-waiver | 0.909 | 0.909 | 0.909 | 22 | 2 |
| collects-contacts-device | 0.643 | 0.6 | 0.621 | 15 | 5 |
| contact-dpo | 0.917 | 1.0 | 0.957 | 11 | 1 |
| minors-protection | 0.615 | 0.727 | 0.667 | 11 | 5 |
| collects-sensitive | 0.857 | 0.667 | 0.75 | 9 | 1 |
| data-sold-or-shared | 0.9 | 1.0 | 0.947 | 9 | 1 |
| default-consent | 1.0 | 0.714 | 0.833 | 7 | 0 |
| can-delete-data | 0.8 | 0.8 | 0.8 | 5 | 1 |
| content-removal-discretion | 1.0 | 0.4 | 0.571 | 5 | 0 |
| account-termination-anytime | 0.429 | 0.75 | 0.545 | 4 | 4 |
| personalized-ads | 1.0 | 1.0 | 1.0 | 4 | 0 |
| terms-change-no-notice | 1.0 | 1.0 | 1.0 | 4 | 0 |
| can-export-data | 0.333 | 0.333 | 0.333 | 3 | 2 |
| easy-account-deletion | 1.0 | 0.667 | 0.8 | 3 | 0 |
| user-indemnifies | 1.0 | 1.0 | 1.0 | 2 | 0 |
| cross-border-transfer | 0.5 | 1.0 | 0.667 | 1 | 1 |
| data-minimization | 0 | 0.0 | 0 | 1 | 0 |
| far-jurisdiction | 0.5 | 1.0 | 0.667 | 1 | 1 |
| gov-disclosure | 1.0 | 1.0 | 1.0 | 1 | 0 |
| hard-account-deletion | 0 | 0.0 | 0 | 1 | 0 |
| indefinite-retention | 0 | 0.0 | 0 | 1 | 0 |
| liability-cap | 0 | 0.0 | 0 | 1 | 0 |
| no-tracking | 1.0 | 1.0 | 1.0 | 1 | 0 |
| you-own-content | 1.0 | 1.0 | 1.0 | 1 | 0 |
| ai-training | 0.0 | 0 | 0 | 0 | 2 |
| broad-content-license | 0.0 | 0 | 0 | 0 | 1 |
| collects-beyond-service | 0.0 | 0 | 0 | 0 | 1 |
