#!/bin/bash -e
# Copy the Home Base source into the image and run its installer in the chroot.
install -d "${ROOTFS_DIR}/tmp/homebase-src"
cp -r files/homebase/. "${ROOTFS_DIR}/tmp/homebase-src/"

on_chroot <<'CHROOT'
SKIP_APT=1 HB_CHROOT=1 sh /tmp/homebase-src/system/install.sh
rm -rf /tmp/homebase-src
# No usable password in the shared image: it is set later in Settings.
usermod -L homebase
CHROOT

# Boot quietly to the TV interface; allow 4K at 60 Hz to be chosen in Settings.
CONFIG="${ROOTFS_DIR}/boot/firmware/config.txt"
grep -q '^hdmi_enable_4kp60=1' "$CONFIG" || printf '\n[all]\nhdmi_enable_4kp60=1\n' >> "$CONFIG"
# A faster, quieter start: no rainbow square, no one-second pause before Linux (the same block homebase-bootcfg edits)
grep -q 'homebase-bootcfg' "$CONFIG" || printf '%s\n' '# >>> Home Base boot settings (homebase-bootcfg)' '[all]' \
  'disable_splash=1' 'boot_delay=0' '# <<< Home Base boot settings' >> "$CONFIG"
CMDLINE="${ROOTFS_DIR}/boot/firmware/cmdline.txt"
# (console=tty1 stays: with no console the boot stalled before the root disk was mounted, and on another VT the TV
# showed that VT rather than Home Base. Raspberry Pi OS keeps it the same way.)
sed -i 's/$/ quiet loglevel=3 logo.nologo vt.global_cursor_default=0/' "$CMDLINE"
# The root partition is grown on first boot by homebase-expand.service, not the initramfs (its disk ID change could
# be lost, leaving the command line pointing at a missing root device): drop the initramfs's resize trigger.
sed -i 's/ resize\b//' "$CMDLINE"
install -m 755 files/homebase/system/homebase-expand "${ROOTFS_DIR}/usr/local/sbin/homebase-expand"
install -m 644 files/homebase/system/homebase-expand.service "${ROOTFS_DIR}/etc/systemd/system/homebase-expand.service"
on_chroot <<'CHROOT'
systemctl enable homebase-expand.service
CHROOT
