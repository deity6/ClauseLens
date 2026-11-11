# 句子级评测（ToS;DR 人工标注，按站点划分）

- train: 18094 句 / 1423 站；test: 4154 句 / 354 站；站点重叠 0

| 方法 | micro P | micro R | micro F1 | macro F1 |
|---|---|---|---|---|
| rule | 0.536 | 0.198 | 0.289 | 0.266 |
| model | 0.778 | 0.692 | 0.733 | 0.716 |
| fused | 0.773 | 0.702 | 0.736 | 0.721 |

## 每标签（fused）

| 标签 | P | R | F1 | test 支持 | 误报 |
|---|---|---|---|---|---|
| tracks-across-sites | 0.809 | 0.688 | 0.744 | 333 | 54 |
| broad-liability-waiver | 0.95 | 0.829 | 0.885 | 251 | 11 |
| personalized-ads | 0.641 | 0.733 | 0.684 | 146 | 60 |
| data-sold-or-shared | 0.72 | 0.615 | 0.664 | 117 | 28 |
| far-jurisdiction | 0.793 | 0.812 | 0.802 | 85 | 18 |
| can-delete-data | 0.781 | 0.61 | 0.685 | 82 | 14 |
| account-termination-anytime | 0.691 | 0.7 | 0.696 | 80 | 25 |
| not-sold | 0.947 | 0.684 | 0.794 | 79 | 3 |
| collects-beyond-service | 0.733 | 0.452 | 0.559 | 73 | 12 |
| user-indemnifies | 0.954 | 0.925 | 0.939 | 67 | 3 |
| terms-change-no-notice | 0.721 | 0.667 | 0.693 | 66 | 17 |
| no-tracking | 0.737 | 0.467 | 0.571 | 60 | 10 |
| cross-border-transfer | 0.868 | 0.836 | 0.852 | 55 | 7 |
| content-removal-discretion | 0.841 | 0.685 | 0.755 | 54 | 7 |
| collects-sensitive | 0.793 | 0.469 | 0.59 | 49 | 6 |
| easy-account-deletion | 0.735 | 0.783 | 0.758 | 46 | 13 |
| data-minimization | 0.378 | 0.311 | 0.341 | 45 | 23 |
| terms-change-notice | 0.455 | 0.444 | 0.449 | 45 | 24 |
| clear-retention | 0.592 | 0.659 | 0.624 | 44 | 20 |
| default-consent | 0.837 | 0.878 | 0.857 | 41 | 7 |
| you-own-content | 0.95 | 0.95 | 0.95 | 40 | 2 |
| broad-content-license | 0.676 | 0.605 | 0.639 | 38 | 11 |
| indefinite-retention | 0.714 | 0.541 | 0.615 | 37 | 8 |
| contact-dpo | 0.75 | 0.844 | 0.794 | 32 | 9 |
| class-action-waiver | 0.897 | 0.929 | 0.912 | 28 | 3 |
| gov-disclosure | 0.524 | 0.815 | 0.638 | 27 | 20 |
| can-export-data | 0.75 | 0.48 | 0.585 | 25 | 4 |
| no-automated-access | 0.885 | 0.92 | 0.902 | 25 | 3 |
| liability-cap | 1.0 | 0.9 | 0.947 | 20 | 0 |
| forced-arbitration | 0.789 | 0.882 | 0.833 | 17 | 4 |
| collects-contacts-device | 0.4 | 0.75 | 0.522 | 8 | 9 |
| notify-breach | 0.857 | 0.857 | 0.857 | 7 | 1 |
| hard-account-deletion | 0.6 | 0.75 | 0.667 | 4 | 2 |

## 每标签（rule，仅规则层）

| 标签 | P | R | F1 | test 支持 | 误报 |
|---|---|---|---|---|---|
| tracks-across-sites | 0.855 | 0.213 | 0.341 | 333 | 12 |
| broad-liability-waiver | 0.975 | 0.155 | 0.268 | 251 | 1 |
| personalized-ads | 0.422 | 0.13 | 0.199 | 146 | 26 |
| data-sold-or-shared | 0.344 | 0.094 | 0.148 | 117 | 21 |
| far-jurisdiction | 0.636 | 0.082 | 0.146 | 85 | 4 |
| can-delete-data | 0.724 | 0.256 | 0.378 | 82 | 8 |
| account-termination-anytime | 0.522 | 0.15 | 0.233 | 80 | 11 |
| not-sold | 0.846 | 0.139 | 0.239 | 79 | 2 |
| collects-beyond-service | 0.0 | 0.0 | 0.0 | 73 | 3 |
| user-indemnifies | 1.0 | 0.836 | 0.911 | 67 | 0 |
| terms-change-no-notice | 0.152 | 0.258 | 0.191 | 66 | 95 |
| no-tracking | 0.267 | 0.267 | 0.267 | 60 | 44 |
| cross-border-transfer | 0.8 | 0.145 | 0.246 | 55 | 2 |
| content-removal-discretion | 0.6 | 0.056 | 0.102 | 54 | 2 |
| collects-sensitive | 0.438 | 0.143 | 0.215 | 49 | 9 |
| easy-account-deletion | 0.36 | 0.196 | 0.254 | 46 | 16 |
| data-minimization | 0.0 | 0.0 | 0.0 | 45 | 0 |
| terms-change-notice | 0.571 | 0.089 | 0.154 | 45 | 3 |
| clear-retention | 0.5 | 0.045 | 0.083 | 44 | 2 |
| default-consent | 0.0 | 0.0 | 0.0 | 41 | 6 |
| you-own-content | 1.0 | 0.35 | 0.519 | 40 | 0 |
| broad-content-license | 0.45 | 0.237 | 0.31 | 38 | 11 |
| indefinite-retention | 0.0 | 0.0 | 0.0 | 37 | 1 |
| contact-dpo | 0.462 | 0.375 | 0.414 | 32 | 14 |
| class-action-waiver | 0.5 | 0.071 | 0.125 | 28 | 2 |
| gov-disclosure | 0.455 | 0.741 | 0.563 | 27 | 24 |
| can-export-data | 0.5 | 0.32 | 0.39 | 25 | 8 |
| no-automated-access | 0.808 | 0.84 | 0.824 | 25 | 5 |
| liability-cap | 0.444 | 0.2 | 0.276 | 20 | 5 |
| forced-arbitration | 0.632 | 0.706 | 0.667 | 17 | 7 |
| collects-contacts-device | 0.2 | 0.625 | 0.303 | 8 | 20 |
| notify-breach | 0.0 | 0.0 | 0.0 | 7 | 0 |
| hard-account-deletion | 0.0 | 0.0 | 0.0 | 4 | 0 |
