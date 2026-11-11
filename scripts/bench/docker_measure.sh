#!/bin/bash
# 测 docker 容器的峰值内存：读 cgroup v2 的 memory.peak（容器私有 scope），
# 容器一退出 scope 就没了，所以必须在跑的时候取。
#   usage: docker_measure.sh <image> [args...]     # 容器内产物请写到 /out（已挂到 ~/bench）
set -u
IMG="$1"; shift
name="meas-$$"
cid=$(sudo docker run -d --name "$name" -v /home/ubuntu/bench:/out "$IMG" "$@")
if [ -z "$cid" ]; then echo "start_failed"; exit 1; fi
pid=$(sudo docker inspect -f '{{.State.Pid}}' "$name" 2>/dev/null)
scope=$(grep -o '/[^ ]*\.scope' "/proc/$pid/cgroup" 2>/dev/null | head -1)
peak=0
while [ "$(sudo docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" = "true" ]; do
  p=$(cat "/sys/fs/cgroup$scope/memory.peak" 2>/dev/null || echo 0)
  if [ "${p:-0}" -gt "$peak" ]; then peak=$p; fi
  sleep 0.25
done
echo "--- container output ---"
sudo docker logs "$name" 2>&1 | tail -6
sudo docker rm -f "$name" >/dev/null 2>&1
echo "PEAK_MB=$((peak / 1048576))"
