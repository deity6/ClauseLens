# 中文规则层评测（test）

## A. CAPP-130 主题级（58 个 App，19562 句）

| 主题 | P | R | F1 | 支持 |
|---|---|---|---|---|
| 共享、委托、转让、公开（披露） | 0.576 | 0.105 | 0.177 | 2464 |
| 特殊人群 | 0.591 | 0.57 | 0.58 | 700 |
| 联系方式 | 0.227 | 0.146 | 0.178 | 342 |
| 数据、权限管理 | 0.738 | 0.14 | 0.236 | 2770 |
| 存储方式 | 0.839 | 0.074 | 0.136 | 703 |
| 隐私政策的授权、修改与变更 | 0.916 | 0.139 | 0.242 | 546 |
| 权限获取 | 0.215 | 0.266 | 0.238 | 912 |

## B. 细标签银标集（400 句）

micro P 0.516 / R 0.403 / F1 0.453

| 标签 | P | R | F1 | 支持 | 误报 |
|---|---|---|---|---|---|
| default-consent | 1.0 | 0.667 | 0.8 | 12 | 0 |
| data-sold-or-shared | 0.385 | 0.455 | 0.417 | 11 | 8 |
| broad-liability-waiver | 0.273 | 0.333 | 0.3 | 9 | 8 |
| user-indemnifies | 1.0 | 0.111 | 0.2 | 9 | 0 |
| can-delete-data | 1.0 | 0.375 | 0.545 | 8 | 0 |
| minors-protection | 0.5 | 0.75 | 0.6 | 8 | 6 |
| collects-contacts-device | 0.75 | 0.429 | 0.545 | 7 | 1 |
| not-sold | 0 | 0.0 | 0 | 5 | 0 |
| terms-change-no-notice | 0.8 | 0.8 | 0.8 | 5 | 1 |
| broad-content-license | 1.0 | 0.5 | 0.667 | 4 | 0 |
| clear-retention | 0 | 0.0 | 0 | 4 | 0 |
| content-removal-discretion | 0.667 | 0.5 | 0.571 | 4 | 1 |
| account-termination-anytime | 0.25 | 0.333 | 0.286 | 3 | 3 |
| collects-sensitive | 0.5 | 0.667 | 0.571 | 3 | 2 |
| cross-border-transfer | 0.5 | 0.333 | 0.4 | 3 | 1 |
| no-automated-access | 0 | 0.0 | 0 | 3 | 0 |
| terms-change-notice | 0.0 | 0.0 | 0 | 3 | 1 |
| ai-training | 1.0 | 1.0 | 1.0 | 2 | 0 |
| can-export-data | 0 | 0.0 | 0 | 2 | 0 |
| contact-dpo | 0.25 | 1.0 | 0.4 | 2 | 6 |
| easy-account-deletion | 0.25 | 0.5 | 0.333 | 2 | 3 |
| far-jurisdiction | 0.0 | 0.0 | 0 | 2 | 1 |
| gov-disclosure | 0 | 0.0 | 0 | 2 | 0 |
| hard-account-deletion | 0 | 0.0 | 0 | 2 | 0 |
| data-minimization | 1.0 | 1.0 | 1.0 | 1 | 0 |
| notify-breach | 0 | 0.0 | 0 | 1 | 0 |
| personalized-ads | 0.0 | 0.0 | 0 | 1 | 1 |
| you-own-content | 1.0 | 1.0 | 1.0 | 1 | 0 |
| no-tracking | 0.0 | 0 | 0 | 0 | 1 |
| tracks-across-sites | 0.0 | 0 | 0 | 0 | 1 |
