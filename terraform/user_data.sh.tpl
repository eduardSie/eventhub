#!/bin/bash
# user_data.sh.tpl — runs ONCE on first boot
# Only job: install Docker + mount the data EBS.
# Everything else (app, .env, seed) is handled by GitHub Actions.
set -euo pipefail
exec > /var/log/user_data.log 2>&1

echo "==> [1/4] System update"
apt-get update -y
apt-get upgrade -y

echo "==> [2/4] Install Docker"
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
usermod -aG docker ubuntu
systemctl enable docker

echo "==> [3/4] Mount data EBS at /var/lib/docker"
DATA_DEVICE="${data_device}"

for i in $(seq 1 12); do
  [ -b "$DATA_DEVICE" ] && break
  echo "Waiting for $DATA_DEVICE... ($i/12)"
  sleep 5
done
[ -b "$DATA_DEVICE" ] || { echo "ERROR: $DATA_DEVICE not found"; exit 1; }

if ! blkid "$DATA_DEVICE" | grep -q TYPE; then
  echo "New volume — formatting as ext4"
  mkfs -t ext4 "$DATA_DEVICE"
fi

UUID=$(blkid -s UUID -o value "$DATA_DEVICE")
mkdir -p /var/lib/docker

if ! grep -q "$UUID" /etc/fstab; then
  echo "UUID=$UUID /var/lib/docker ext4 defaults,nofail 0 2" >> /etc/fstab
fi
mount -a

systemctl start docker

echo "==> [4/4] Create app directory"
mkdir -p "${app_dir}"
chown ubuntu:ubuntu "${app_dir}"

echo "Bootstrap complete — waiting for GitHub Actions to deploy the app"
