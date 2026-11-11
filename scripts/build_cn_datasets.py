"""把公开中文隐私政策数据集（CAPP-130、CA4P-483）的 tarball 转成统一 jsonl。

tarball 视为不可信数据：只以文本方式读取成员，不解压、不执行其中任何脚本。

用法：python scripts/build_cn_datasets.py
输入：data/raw/datasets/CAPP-130/repo.tgz、data/raw/datasets/CA4P-483/repo.tgz（缺失则跳过）
输出：
  data/processed/capp130_docs.jsonl      {app, doc_type, text, chars, source, license}
  data/processed/capp130_sentences.jsonl {app, id, text, label, rewrite, source, license}
  data/processed/ca4p483_docs.jsonl      {app(=文件编号), doc_type, text, chars, path, source, license}（标注保留在 raw）
"""
from __future__ import annotations

import json
import re
import tarfile
from pathlib import Path, PurePosixPath

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "datasets"
PROC = ROOT / "data" / "processed"
MAX_MEMBER = 20 * 1024 * 1024


def read(tf: tarfile.TarFile, m: tarfile.TarInfo) -> str:
    f = tf.extractfile(m)
    data = f.read() if f else b""
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def capp130() -> None:
    tgz = RAW / "CAPP-130" / "repo.tgz"
    if not tgz.exists():
        print("CAPP-130 缺失，跳过")
        return
    lic = "Data: CC BY 4.0; Code: Apache-2.0 (EnlightenedAI/CAPP-130)"
    src = "github.com/EnlightenedAI/CAPP-130"
    nd = ns = chars = 0
    task_app: dict[str, str] = {}
    with tarfile.open(tgz, "r:gz") as tf, \
            (PROC / "capp130_docs.jsonl").open("w", encoding="utf-8", newline="\n") as fd, \
            (PROC / "capp130_sentences.jsonl").open("w", encoding="utf-8", newline="\n") as fs:
        for m in tf:
            if not m.isfile() or m.size > MAX_MEMBER:
                continue
            p = PurePosixPath(m.name)
            if "Original_policies" in p.parts and p.suffix == ".txt":
                text = read(tf, m)
                fd.write(json.dumps({"app": p.stem, "doc_type": "privacy", "text": text, "chars": len(text),
                                     "source": src, "license": lic}, ensure_ascii=False) + "\n")
                nd += 1
                chars += len(text)
            elif p.parent.name == "Annotation" and p.suffix == ".jsonl":
                lines = [json.loads(l) for l in read(tf, m).splitlines() if l.strip()]
                app = lines[0]["text"] if lines else p.stem  # 首句通常是「XX隐私政策」标题
                task_app[p.stem] = app
                for r in lines:
                    fs.write(json.dumps({"app": app, "task": p.stem, "id": r.get("id"), "text": r.get("text", ""),
                                         "label": r.get("label", []), "rewrite": r.get("rewrite", []),
                                         "source": src, "license": lic}, ensure_ascii=False) + "\n")
                    ns += 1
    print(f"CAPP-130：原文 {nd} 篇（{chars} 字），标注句 {ns} 条（{len(task_app)} 个文件）")


def ca4p483() -> None:
    tgz = RAW / "CA4P-483" / "repo.tgz"
    if not tgz.exists():
        print("CA4P-483 缺失，跳过")
        return
    lic = "Academic/research use only; commercial use requires author permission (zacharykzhao/CA4P-483 LICENSE.md)"
    src = "github.com/zacharykzhao/CA4P-483"
    n = chars = 0
    try:
        with tarfile.open(tgz, "r:gz") as tf, \
                (PROC / "ca4p483_docs.jsonl").open("w", encoding="utf-8", newline="\n") as fd:
            for m in tf:
                p = PurePosixPath(m.name)
                if not m.isfile() or m.size > MAX_MEMBER or "raw_data" not in p.parts or p.suffix not in (".html", ".txt"):
                    continue
                text = read(tf, m)
                if p.suffix == ".html":
                    soup = BeautifulSoup(text, "lxml")
                    for t in soup(("script", "style", "noscript")):
                        t.decompose()
                    text = "\n".join(l.strip() for l in soup.get_text("\n").splitlines() if l.strip())
                if len(text.strip()) < 200:
                    continue
                mm = re.search(r"Apkid:\s*([\w.]+)", text[:500])
                fd.write(json.dumps({"app": mm.group(1) if mm else p.stem, "doc_type": "privacy", "text": text, "chars": len(text),
                                     "path": "/".join(p.parts[1:]), "source": src, "license": lic},
                                    ensure_ascii=False) + "\n")
                n += 1
                chars += len(text)
    except (tarfile.TarError, EOFError, OSError) as e:
        print(f"CA4P-483 读取中断：{e}")
    print(f"CA4P-483：原文 {n} 篇（{chars} 字）")


if __name__ == "__main__":
    PROC.mkdir(parents=True, exist_ok=True)
    capp130()
    ca4p483()
