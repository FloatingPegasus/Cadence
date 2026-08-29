#!/bin/sh
# Bootstrap an Ubuntu 24.04 host for Cadence (Docker + Compose plugin).
# Run as root or with sudo: ./scripts/bootstrap-host.sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo ./scripts/bootstrap-host.sh)" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes ca-certificates curl gnupg ufw

install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install --yes docker-ce docker-ce-cli containerd.io docker-compose-plugin

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

systemctl enable --now docker
docker version
docker compose version
echo "Host ready. Clone Cadence and run scripts/deploy-prod.sh"
