---
title: "Backlight"
---

## sysfs

By default, the backlight uses the sysfs backlight interface. This should work out of the box on most laptops.

## ddc/ci

With DDC/CI, we can control the backlight on regular monitors. Though a lot of monitors have an incomplete implementation of DDC, usually omitting input switching, backlight control is usually implemented.

### Enable i2c-dev
DDC/CI uses i2c, so you need to enable the i2c module. This can be done with `modprobe i2c`, or permanently on Arch with this file:

```conf {filename="/etc/modules-load.d/i2c-dev.conf"}
i2c-dev
```

### User permissions
Unpriveleged users don't have access to i2c by default, so you need to add your user to the `i2c` group:

```
sudo usermod -aG i2c "${USER}"
```

### Log out/reboot
Adding your user to a group requires logging out of your user session, so either log out or reboot to load the i2c kernel module if you didn't `modprobe` it.
