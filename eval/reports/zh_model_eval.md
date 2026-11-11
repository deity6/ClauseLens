# 中文细标签评测（test：27 个独立站点、330 句人工标注，已去泄漏）

训练 2000 句 / 阈值调参 400 句（均来自 dev 站点）

| 方法 | P | R | F1 |
|---|---|---|---|
| rule | 0.507 | 0.381 | 0.435 |
| model | 0.677 | 0.433 | 0.528 |
| fused | 0.646 | 0.546 | 0.592 |

## fused 每标签

| 标签 | P | R | F1 | 支持 | 误报 |
|---|---|---|---|---|---|
| default-consent | 1.0 | 0.7 | 0.824 | 10 | 0 |
| minors-protection | 0.6 | 0.75 | 0.667 | 8 | 4 |
| broad-liability-waiver | 0.3 | 0.429 | 0.353 | 7 | 7 |
| data-sold-or-shared | 0.6 | 0.429 | 0.5 | 7 | 2 |
| user-indemnifies | 1.0 | 0.714 | 0.833 | 7 | 0 |
| can-delete-data | 0.8 | 0.8 | 0.8 | 5 | 1 |
| collects-contacts-device | 0.75 | 0.6 | 0.667 | 5 | 1 |
| terms-change-no-notice | 0.444 | 0.8 | 0.571 | 5 | 5 |
| broad-content-license | 1.0 | 0.5 | 0.667 | 4 | 0 |
| content-removal-discretion | 1.0 | 0.25 | 0.4 | 4 | 0 |
| not-sold | 0 | 0.0 | 0 | 4 | 0 |
| account-termination-anytime | 1.0 | 0.667 | 0.8 | 3 | 0 |
| terms-change-notice | 1.0 | 0.333 | 0.5 | 3 | 0 |
| ai-training | 1.0 | 1.0 | 1.0 | 2 | 0 |
| can-export-data | 0 | 0.0 | 0 | 2 | 0 |
| clear-retention | 0 | 0.0 | 0 | 2 | 0 |
| collects-sensitive | 0.5 | 0.5 | 0.5 | 2 | 1 |
| contact-dpo | 0.333 | 1.0 | 0.5 | 2 | 4 |
| cross-border-transfer | 1.0 | 0.5 | 0.667 | 2 | 0 |
| far-jurisdiction | 0.0 | 0.0 | 0 | 2 | 1 |
| gov-disclosure | 1.0 | 1.0 | 1.0 | 2 | 0 |
| hard-account-deletion | 0 | 0.0 | 0 | 2 | 0 |
| no-automated-access | 0 | 0.0 | 0 | 2 | 0 |
| data-minimization | 1.0 | 1.0 | 1.0 | 1 | 0 |
| easy-account-deletion | 0 | 0.0 | 0 | 1 | 0 |
| notify-breach | 1.0 | 1.0 | 1.0 | 1 | 0 |
| personalized-ads | 0.333 | 1.0 | 0.5 | 1 | 2 |
| you-own-content | 1.0 | 1.0 | 1.0 | 1 | 0 |
| no-tracking | 0.0 | 0 | 0 | 0 | 1 |
