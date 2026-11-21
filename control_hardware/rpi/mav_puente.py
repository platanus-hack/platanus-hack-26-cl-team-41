"""Puente MAVLink en la Raspberry Pi: UART de la H743 (/dev/ttyAMA0, 115200) <-> UDP puerto 14550.
Reenvia bytes sin interpretarlos. Los datos de la H743 van a todos los clientes UDP vistos en los ultimos 10 s
(el PC se anuncia mandando cualquier paquete MAVLink, por ejemplo un heartbeat).
PC: pymavlink.mavutil.mavlink_connection("udpout:172.16.0.127:14550")  (o QGroundControl/Mission Planner)
"""
import select, socket, time
import serial

ser = serial.Serial("/dev/ttyAMA0", 115200, timeout=0)
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind(("0.0.0.0", 14550))
peers = {}
print("puente MAVLink: /dev/ttyAMA0 <-> udp 14550", flush=True)
while True:
    r, _, _ = select.select([ser.fileno(), udp], [], [], 0.05)
    now = time.time()
    if udp in r:
        data, addr = udp.recvfrom(4096)
        if addr not in peers:
            print("cliente", addr, flush=True)
        peers[addr] = now
        ser.write(data)
    if ser.fileno() in r:
        data = ser.read(4096)
        for a, t in list(peers.items()):
            if now - t > 10:
                del peers[a]
            else:
                udp.sendto(data, a)
