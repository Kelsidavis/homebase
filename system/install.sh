#!/bin/sh
# Install or update Home Base on Raspberry Pi OS Lite (64-bit, trixie).
#
#   sudo sh system/install.sh            # on a running Pi
#   HB_CHROOT=1 sh system/install.sh     # inside the image build (pi-gen)
#
# Set SKIP_APT=1 to skip package installation.
set -e
SRC=$(cd "$(dirname "$0")/.." && pwd)
USER_NAME=homebase
APP=/opt/homebase

if ! id "$USER_NAME" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "Home Base" "$USER_NAME"
fi
for g in audio video render input plugdev netdev; do
  getent group "$g" >/dev/null && adduser "$USER_NAME" "$g" >/dev/null
done
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6)

if [ "${SKIP_APT:-0}" != 1 ]; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    cage chromium wlr-randr pipewire pipewire-pulse wireplumber curl \
    mpv libmpv2 python3-venv fonts-dejavu-core fonts-liberation2 v4l-utils plymouth plymouth-label
fi
# Real-time scheduling for PipeWire's audio thread (the pipewire group's limits): without it, sound crackles
# whenever the CPU is busy.
getent group pipewire >/dev/null && adduser "$USER_NAME" pipewire >/dev/null

# Boot splash: the Home Base name and three pulsing dots from early boot, so a starting box never looks stalled on a
# black screen. Its last frame stays up (--retain-splash) until Home Base takes over the display.
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
  install -d /usr/share/plymouth/themes/homebase
  install -m 644 "$SRC"/system/plymouth/homebase/* /usr/share/plymouth/themes/homebase/
  plymouth-set-default-theme homebase
  install -d /etc/systemd/system/plymouth-quit.service.d
  printf '[Service]\nExecStart=\nExecStart=-/usr/bin/plymouth quit --retain-splash\n' \
    > /etc/systemd/system/plymouth-quit.service.d/homebase.conf
  CMDLINE=/boot/firmware/cmdline.txt
  if [ -f "$CMDLINE" ] && ! grep -qw splash "$CMDLINE"; then sed -i '1 s/$/ splash/' "$CMDLINE"; fi
  update-initramfs -u -k all >/dev/null   # (the splash starts from the initramfs)
fi

# Application files
install -d -o "$USER_NAME" -g "$USER_NAME" "$APP"
for d in backend ui chromium-ext bin; do
  rm -rf "${APP:?}/$d"
  cp -r "$SRC/$d" "$APP/$d"
done
chmod +x "$APP"/bin/*

# Plex cast receiver in its own virtualenv
if [ ! -x "$APP/venv/bin/plex-mpv-shim" ]; then
  python3 -m venv "$APP/venv"
  "$APP/venv/bin/pip" install --no-cache-dir --quiet plex-mpv-shim
fi
# YouTube: yt-dlp with its challenge solver scripts, and Deno, the JavaScript runtime it needs (Home Base keeps
# yt-dlp up to date itself)
"$APP/venv/bin/pip" install --no-cache-dir --quiet -U "yt-dlp[default]" deno segno   # (segno: the sign-in QR code)
chown -R "$USER_NAME:$USER_NAME" "$APP"

# Browser policy
install -d /etc/chromium/policies/managed
install -m 644 "$SRC/system/chromium-policy.json" /etc/chromium/policies/managed/homebase.json

# Privileges: only the commands the interface needs, no general passwordless sudo
install -m 755 "$SRC/system/homebase-setpass" /usr/local/sbin/homebase-setpass
rm -f /etc/sudoers.d/010_pi-nopasswd /etc/sudoers.d/010_homebase-nopasswd
install -m 440 "$SRC/system/sudoers" /etc/sudoers.d/020_homebase
visudo -cf /etc/sudoers.d/020_homebase >/dev/null
adduser "$USER_NAME" sudo >/dev/null

# SSH stays off until turned on in Settings (which requires a password)
install -d /etc/ssh/sshd_config.d
install -m 644 "$SRC/system/sshd-homebase.conf" /etc/ssh/sshd_config.d/10-homebase.conf

# Log in on the TV console automatically and start the kiosk from the login shell
install -d /etc/systemd/system/getty@tty1.service.d
install -m 644 "$SRC/system/autologin.conf" /etc/systemd/system/getty@tty1.service.d/autologin.conf
install -m 644 -o "$USER_NAME" -g "$USER_NAME" "$SRC/system/bash_profile" "$USER_HOME/.bash_profile"

# User services: the backend and the cast receiver, started at boot
UNITS="$USER_HOME/.config/systemd/user"
install -d -o "$USER_NAME" -g "$USER_NAME" "$USER_HOME/.config" "$USER_HOME/.config/systemd" "$UNITS" "$UNITS/default.target.wants"
for unit in homebase.service plex-mpv-shim.service; do
  install -m 644 -o "$USER_NAME" -g "$USER_NAME" "$SRC/system/$unit" "$UNITS/$unit"
  ln -sf "../$unit" "$UNITS/default.target.wants/$unit"
  chown -h "$USER_NAME:$USER_NAME" "$UNITS/default.target.wants/$unit"
done
# Sound: prefer the TV's HDMI over the headphone jack
WP="$USER_HOME/.config/wireplumber/wireplumber.conf.d"
install -d -o "$USER_NAME" -g "$USER_NAME" "$USER_HOME/.config/wireplumber" "$WP"
install -m 644 -o "$USER_NAME" -g "$USER_NAME" "$SRC/system/wireplumber-hdmi.conf" "$WP/50-homebase-hdmi.conf"

install -d /var/lib/systemd/linger
touch "/var/lib/systemd/linger/$USER_NAME"

if [ "${HB_CHROOT:-0}" != 1 ]; then
  systemctl daemon-reload
  echo "Installed. Reboot to start Home Base: sudo reboot"
fi
