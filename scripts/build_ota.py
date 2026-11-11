"""从 Open Terms Archive *-versions 仓库 tarball 提取各服务各类文档的最新版本。

仓库 main 分支只保存每个文档的当前版本，目录结构 <服务名>/<文档类型>.md。
tarball 视为不可信数据：只以文本方式读取 .md 成员，不解压、不执行任何内容。

用法：python scripts/build_ota.py [data/raw/ota]
输出：data/processed/ota_docs.jsonl，并打印统计。
"""
from __future__ import annotations

import json
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "ota_docs.jsonl"
MAX_MEMBER = 20 * 1024 * 1024

STOP = {
    "en": "the and of to in is that for you your we our with this are be or by on as not any may".split(),
    "fr": "le la les des et de du vous nous est pour dans une sur par que qui ou pas vos votre".split(),
    "de": "der die das und ist sie wir nicht mit von zu den für auf ihre oder ein eine dem".split(),
    "es": "el la los las y de que en para por con usted nosotros una del su sus o no se".split(),
    "it": "il la di e che per con una del della dei gli le non sono suoi tuo tuoi".split(),
    "pt": "o a os as e de que em para com uma do da dos não você seu sua nós".split(),
    "nl": "de het en van een is dat voor met op niet u uw wij ons zijn aan".split(),
}


def detect_lang(text: str) -> str:
    sample = text[:20000]
    if not sample.strip():
        return "unknown"
    cjk = len(re.findall(r"[一-鿿]", sample))
    kana = len(re.findall(r"[぀-ヿ]", sample))
    hangul = len(re.findall(r"[가-힯]", sample))
    letters = len(re.findall(r"\w", sample)) or 1
    if kana > 0.05 * letters:
        return "ja"
    if hangul > 0.2 * letters:
        return "ko"
    if cjk > 0.2 * letters:
        return "zh"
    if len(re.findall(r"[а-яА-Я]", sample)) > 0.3 * letters:
        return "ru"
    words = Counter(re.findall(r"[a-zà-ÿ]+", sample.lower()))
    scores = {lg: sum(words[w] for w in ws) for lg, ws in STOP.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 5 else "unknown"


def main() -> None:
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw" / "ota"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[tuple[str, str, str], int] = {}
    stats = Counter()
    services: dict[str, set] = {}
    langs = Counter()
    n = 0
    with OUT.open("w", encoding="utf-8", newline="\n") as out:
        for tgz in sorted(raw.glob("*-versions/repo.tgz")):
            repo = tgz.parent.name
            try:
                tf = tarfile.open(tgz, "r:gz")
            except (tarfile.TarError, OSError) as e:
                print(f"跳过 {repo}: {e}")
                continue
            with tf:
                for m in tf:
                    if not m.isfile() or not m.name.endswith(".md") or m.size > MAX_MEMBER:
                        continue
                    parts = m.name.split("/")
                    if len(parts) != 3:  # <root>/<service>/<doc>.md；跳过根目录 README 等
                        continue
                    service, doc_type = parts[1], parts[2][:-3]
                    f = tf.extractfile(m)
                    if f is None:
                        continue
                    text = f.read().decode("utf-8", errors="replace").replace("\r\n", "\n")
                    if len(text.strip()) < 200:
                        stats["too_short"] += 1
                        continue
                    lang = detect_lang(text)
                    key = (service, doc_type, text[:2000])
                    if key in seen:  # 同一服务同一文档在多个仓库重复收录
                        stats["dup"] += 1
                        continue
                    seen[key] = 1
                    out.write(json.dumps({"service": service, "doc_type": doc_type, "lang": lang, "text": text,
                                          "source_repo": f"OpenTermsArchive/{repo}", "chars": len(text)},
                                         ensure_ascii=False) + "\n")
                    n += 1
                    stats[repo] += 1
                    stats["chars"] += len(text)
                    services.setdefault(service, set()).add(repo)
                    langs[lang] += 1
    print(f"文档 {n}，服务 {len(services)}，总字符 {stats['chars']}，去重 {stats['dup']}，过短 {stats['too_short']}")
    print("语言：", dict(langs.most_common()))
    print("各仓库：", {k: v for k, v in stats.items() if k.endswith("-versions")})


if __name__ == "__main__":
    main()
