"""Configura el primer arranque (cloud-init) de Raspberry Pi OS en la particion bootfs de la microSD.
Uso: python preparar_boot.py E:\\

- hostname rover, usuario pi con la clave SSH del PC (~/.ssh/id_ed25519_radxa.pub) y sudo sin contrasena
- contrasena de consola: hash en ~/.rover/pi_hash.txt (el texto esta en ~/.rover/credenciales.txt, fuera de OneDrive)
- Ethernet con DHCP + direccion local automatica (169.254.x.x): el PC la encuentra como rover.local
- WiFi: conserva las redes de ~/.rover/network-config.anterior y agrega las de ~/.rover/wifi_extra.yaml si existe
- UART0 en los pines 8/10 (GPIO14/15) -> /dev/ttyAMA0 para la Matek H743
"""
import os, sys, time

boot = sys.argv[1]
home = os.path.expanduser("~")
key = open(os.path.join(home, ".ssh", "id_ed25519_radxa.pub")).read().strip()
pw_hash = open(os.path.join(home, ".rover", "pi_hash.txt")).read().strip()
inst = "rover-%d" % int(time.time())

user_data = f"""#cloud-config
hostname: rover
manage_etc_hosts: true
timezone: America/Santiago
keyboard:
  model: pc105
  layout: "us"
users:
- name: pi
  groups: users,adm,dialout,audio,netdev,video,plugdev,cdrom,games,input,gpio,spi,i2c,render,sudo
  shell: /bin/bash
  lock_passwd: false
  passwd: {pw_hash}
  sudo: ALL=(ALL) NOPASSWD:ALL
  ssh_authorized_keys:
  - {key}
enable_ssh: true
ssh_pwauth: true
rpi:
  interfaces:
    serial: true
"""

# redes WiFi guardadas (sin mostrarlas)
wifi = ""
for fn in ("network-config.anterior", "wifi_extra.yaml"):
    p = os.path.join(home, ".rover", fn)
    if os.path.exists(p):
        lines = open(p).read().splitlines()
        if "wifis:" in "\n".join(lines):
            start = next(i for i, l in enumerate(lines) if l.strip() == "wifis:")
            wifi = "\n".join(lines[start:]) + "\n"
net = """network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      dhcp6: true
      link-local: [ipv4, ipv6]
      optional: true
""" + wifi

open(os.path.join(boot, "user-data"), "w", newline="\n").write(user_data)
open(os.path.join(boot, "network-config"), "w", newline="\n").write(net)
open(os.path.join(boot, "meta-data"), "w", newline="\n").write("instance-id: %s\n" % inst)

cfg_p = os.path.join(boot, "config.txt")
cfg = open(cfg_p).read()
if "dtparam=uart0=on" not in cfg:
    cfg = cfg.rstrip("\n") + "\n\n[all]\n# Rover: UART0 en GPIO14/15 (pines 8/10) para la Matek H743 -> /dev/ttyAMA0\ndtparam=uart0=on\n"
    open(cfg_p, "w", newline="\n").write(cfg)

cl_p = os.path.join(boot, "cmdline.txt")
cl = open(cl_p).read().strip()
cl = " ".join(t for t in cl.split() if not t.startswith("ds=nocloud"))
cl += " ds=nocloud;i=%s" % inst
open(cl_p, "w", newline="\n").write(cl + "\n")

print("bootfs listo:", inst, "| wifi conservado:", bool(wifi))
print("cmdline:", cl.replace(pw_hash, ""))
