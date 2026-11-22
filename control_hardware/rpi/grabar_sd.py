"""Graba una imagen .img.xz de Raspberry Pi OS en la microSD (Windows, requiere administrador).
Uso (PowerShell como administrador):  python grabar_sd.py <imagen.img.xz> <numero_de_disco>

Se niega a escribir si el disco no parece una microSD: tiene que ser extraible/lector de tarjetas,
de menos de 130 GB y no ser el disco del sistema.
"""
import ctypes, json, lzma, subprocess, sys, time

img, num = sys.argv[1], int(sys.argv[2])


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout


info = json.loads(ps("Get-Disk -Number %d | Select-Object Number,FriendlyName,BusType,Size,IsSystem,IsBoot | ConvertTo-Json" % num))
print("Disco:", info)
if info["IsSystem"] or info["IsBoot"] or info["Size"] > 130e9 or not any(
        k in (info["FriendlyName"] or "") for k in ("Reader", "SD", "Card", "USB", "MMC")):
    sys.exit("ABORTADO: el disco %d no parece una microSD" % num)

print("Borrando particiones de la microSD (Windows no deja escribir sobre volumenes montados)...")
import tempfile, os
dp = os.path.join(tempfile.gettempdir(), "rover_diskpart.txt")
open(dp, "w").write("select disk %d\nclean\nrescan\n" % num)
r = subprocess.run(["diskpart", "/s", dp], capture_output=True, text=True)
print(r.stdout[-400:])
time.sleep(3)
parts = ps("(Get-Partition -DiskNumber %d -ErrorAction SilentlyContinue | Measure-Object).Count" % num).strip()
print("Particiones que quedan:", parts)
if parts not in ("0", ""):
    sys.exit("ABORTADO: no se pudieron borrar las particiones")

GENERIC_WRITE, OPEN_EXISTING = 0x40000000, 3
FILE_SHARE_RW = 0x1 | 0x2
k32 = ctypes.windll.kernel32
k32.CreateFileW.restype = ctypes.c_void_p
h = k32.CreateFileW("\\\\.\\PhysicalDrive%d" % num, GENERIC_WRITE, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
if h in (None, ctypes.c_void_p(-1).value):
    sys.exit("No se pudo abrir el disco (falta administrador?) error %d" % k32.GetLastError())

CH = 4 * 1024 * 1024
written = 0
t0 = time.time()
buf = b""
wrote = ctypes.c_ulong(0)


def put(data):
    global written
    if not k32.WriteFile(ctypes.c_void_p(h), data, len(data), ctypes.byref(wrote), None):
        raise OSError("WriteFile fallo, error %d" % k32.GetLastError())
    written += wrote.value


mbr = None   # la tabla de particiones se escribe al final: si va primero, Windows monta bootfs y bloquea el resto
try:
    with lzma.open(img, "rb") as f:
        while True:
            d = f.read(CH)
            if not d:
                break
            if mbr is None:
                mbr = d[:512]; d = b"\0" * 512 + d[512:]
            buf += d
            n = len(buf) // 512 * 512
            if n:
                put(buf[:n]); buf = buf[n:]
            if written and written % (256 * 1024 * 1024) < CH:
                print("  %d MB (%.0f s)" % (written // 2**20, time.time() - t0), flush=True)
        if buf:
            put(buf + b"\0" * (512 - len(buf) % 512))
    k32.FlushFileBuffers(ctypes.c_void_p(h))
    k32.SetFilePointerEx(ctypes.c_void_p(h), ctypes.c_longlong(0), None, 0)
    put(mbr)
    k32.FlushFileBuffers(ctypes.c_void_p(h))
    print("tabla de particiones escrita")
finally:
    k32.CloseHandle(ctypes.c_void_p(h))
    ps("Update-HostStorageCache")
print("LISTO: %d MB escritos en %.0f s" % (written // 2**20, time.time() - t0))
