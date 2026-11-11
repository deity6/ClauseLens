"""ToS;DR case_id → ClauseLens 标签的人工映射表（依据 case 标题逐条审定，替代正则映射）。

原则：只映射语义一致的 case；极性必须与本项目标签一致；一个 case 可映射多个标签。
修改此表后重跑 scripts/train_model.py。
"""

CASE_TAGS: dict[int, list[str]] = {
    # privacy
    400: ["collects-sensitive"], 397: ["collects-sensitive"], 487: ["collects-sensitive", "personalized-ads"],
    373: ["collects-sensitive"],
    322: ["collects-contacts-device"], 323: ["tracks-across-sites"],
    325: ["tracks-across-sites"], 128: ["tracks-across-sites", "personalized-ads"], 217: ["tracks-across-sites"],
    127: ["tracks-across-sites"], 129: ["tracks-across-sites"], 307: ["tracks-across-sites"], 387: ["tracks-across-sites"],
    233: ["tracks-across-sites"], 478: ["tracks-across-sites"],
    216: ["personalized-ads"], 220: ["personalized-ads"], 336: ["personalized-ads"],
    376: ["collects-beyond-service"], 409: ["collects-beyond-service"], 211: ["collects-beyond-service"],
    382: ["collects-beyond-service"],
    196: ["data-minimization"], 298: ["data-minimization"], 176: ["data-minimization"],
    218: ["no-tracking"], 381: ["no-tracking"], 383: ["no-tracking"], 192: ["no-tracking"], 385: ["no-tracking"],
    # sharing
    243: ["data-sold-or-shared"], 166: ["data-sold-or-shared"], 396: ["data-sold-or-shared"], 188: ["data-sold-or-shared"],
    193: ["not-sold"], 311: ["not-sold"], 296: ["not-sold"],
    187: ["cross-border-transfer"], 411: ["cross-border-transfer"],
    164: ["gov-disclosure"],
    391: ["notify-breach"],
    # rights
    195: ["can-delete-data"], 175: ["can-delete-data"],
    140: ["can-export-data"], 184: ["can-export-data"],
    170: ["easy-account-deletion"],
    174: ["hard-account-deletion"], 304: ["indefinite-retention"], 178: ["indefinite-retention"], 333: ["indefinite-retention"],
    303: ["clear-retention"], 177: ["clear-retention"],
    300: ["contact-dpo"],
    # control
    121: ["terms-change-no-notice"], 497: ["terms-change-no-notice"],
    124: ["terms-change-notice"], 123: ["terms-change-notice"], 122: ["terms-change-notice"],
    201: ["account-termination-anytime"], 205: ["account-termination-anytime"],
    202: ["content-removal-discretion"], 377: ["content-removal-discretion"], 310: ["content-removal-discretion"],
    403: ["default-consent"],
    150: ["no-automated-access"],
    # liability
    293: ["broad-liability-waiver"], 286: ["broad-liability-waiver"], 287: ["broad-liability-waiver"],
    186: ["broad-liability-waiver"], 288: ["broad-liability-waiver"],
    149: ["liability-cap"],
    339: ["forced-arbitration"], 117: ["class-action-waiver"],
    242: ["far-jurisdiction"], 163: ["far-jurisdiction"],
    146: ["user-indemnifies"], 145: ["user-indemnifies"], 147: ["user-indemnifies"],
    # content
    134: ["broad-content-license"], 130: ["broad-content-license"], 173: ["broad-content-license"], 139: ["broad-content-license"],
    183: ["you-own-content"],
}
