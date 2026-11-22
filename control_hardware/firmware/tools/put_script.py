"""Sube un .lua a /APM/scripts de la placa por MAVFTP y reinicia scripting. Uso: python put_script.py COM4 archivo.lua"""
import sys, os, time
from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP
m=mavutil.mavlink_connection(sys.argv[1],baud=115200); m.wait_heartbeat(timeout=10)
ftp=MAVFTP(m,m.target_system,m.target_component)
dst="/APM/scripts/"+os.path.basename(sys.argv[2])
r=ftp.cmd_put([sys.argv[2],dst]); r2=ftp.process_ftp_reply("CreateFile", timeout=10)
print("put", dst, r.error_code, r2.error_code)
ftp.cmd_list(["/APM/scripts"]); print([(e.name,e.size_b) for e in ftp.list_result])
