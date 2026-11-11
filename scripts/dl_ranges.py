"""并发分片下载（Range），可断点续传。用法：python scripts/dl_ranges.py URL OUT SIZE [N]"""
import os
import sys
import threading
import time

import requests

url, out, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
n = int(sys.argv[4]) if len(sys.argv) > 4 else 16
ch = (size + n - 1) // n
os.makedirs(out + ".parts", exist_ok=True)


def work(i):
    a = i * ch
    b = min(size, a + ch) - 1
    p = os.path.join(out + ".parts", f"{i:03d}")
    for attempt in range(30):
        have = os.path.getsize(p) if os.path.exists(p) else 0
        if have >= b - a + 1:
            return
        try:
            with requests.get(url, headers={"Range": f"bytes={a + have}-{b}"}, stream=True, timeout=60) as r:
                if r.status_code != 206:
                    raise RuntimeError(r.status_code)
                with open(p, "ab") as f:
                    for c in r.iter_content(65536):
                        f.write(c)
        except Exception as e:
            print(f"part {i} retry {attempt}: {e}", flush=True)
            time.sleep(3)


ts = [threading.Thread(target=work, args=(i,)) for i in range(n)]
for t in ts:
    t.start()
while any(t.is_alive() for t in ts):
    time.sleep(30)
    got = sum(os.path.getsize(os.path.join(out + ".parts", f)) for f in os.listdir(out + ".parts"))
    print(f"{got}/{size} {got * 100 // size}%", flush=True)
got = sum(os.path.getsize(os.path.join(out + ".parts", f)) for f in os.listdir(out + ".parts"))
if got == size:
    with open(out, "wb") as f:
        for i in range(n):
            with open(os.path.join(out + ".parts", f"{i:03d}"), "rb") as g:
                f.write(g.read())
    print("DONE", out)
else:
    print("INCOMPLETE", got, size)
