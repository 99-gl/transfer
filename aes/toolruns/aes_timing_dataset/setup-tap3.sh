#!/usr/bin/env bash
# Usage: sudo ./setup-tap3.sh
# Creates the isolated tap3 / 172.16.2.0/24 network for the dataset VM clone.
set -euo pipefail
TAP_DEV=tap3
HOST_IP=172.16.2.1
GUEST_CIDR=172.16.2.0/24
OUT_IF=${OUT_IF:-}
if [[ -z "$OUT_IF" ]]; then OUT_IF=$(ip route get 8.8.8.8 | awk '{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}'); fi
ip tuntap add dev "$TAP_DEV" mode tap 2>/dev/null || true
ip addr flush dev "$TAP_DEV" || true
ip addr add "$HOST_IP/24" dev "$TAP_DEV"
ip link set "$TAP_DEV" up
sysctl -w net.ipv4.ip_forward=1 >/dev/null
iptables -t nat -C POSTROUTING -s "$GUEST_CIDR" -o "$OUT_IF" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "$GUEST_CIDR" -o "$OUT_IF" -j MASQUERADE
iptables -C FORWARD -i "$TAP_DEV" -o "$OUT_IF" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "$TAP_DEV" -o "$OUT_IF" -j ACCEPT
iptables -C FORWARD -i "$OUT_IF" -o "$TAP_DEV" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "$OUT_IF" -o "$TAP_DEV" -m state --state RELATED,ESTABLISHED -j ACCEPT
echo "$TAP_DEV host=$HOST_IP guest=172.16.2.2 out=$OUT_IF"
