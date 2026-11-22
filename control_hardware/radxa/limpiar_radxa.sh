#!/bin/sh
# Deja la Radxa Zero 3W liviana para el rover. No borra archivos: solo desactiva el arranque automatico.
# Ejecutar como root:  sudo sh /var/tmp/limpiar_radxa.sh
# Para revertir:       sudo systemctl enable --now skydock.service && sudo systemctl set-default graphical.target
set -e

echo "== 1. SkyDock (proyecto anterior: usa la camara, /dev/ttyS5 y manda comandos MAVLink) =="
systemctl disable --now skydock.service || true

echo "== 2. Escritorio grafico (no hace falta en el robot) =="
systemctl set-default multi-user.target
systemctl stop lightdm.service 2>/dev/null || true

echo "== 3. Impresoras (CUPS) =="
systemctl disable --now cups.path cups.service cups-browsed.service 2>/dev/null || true

echo
echo "== Estado =="
echo "skydock:  $(systemctl is-enabled skydock.service 2>/dev/null) / $(systemctl is-active skydock.service 2>/dev/null)"
echo "arranque: $(systemctl get-default)"
echo "lightdm:  $(systemctl is-active lightdm.service 2>/dev/null)"
echo "Procesos que mas usan CPU:"
ps -eo pid,user,%cpu,%mem,args --sort=-%cpu | head -8
echo "Listo. Los archivos de SkyDock siguen en /var/tmp/skydock."
