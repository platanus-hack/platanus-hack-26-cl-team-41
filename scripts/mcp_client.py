"""Minimal MCP stdio client for solidcraft-cli.
usage: python mcp.py <calls.json> [extra cli args...]
calls.json: list of {"tool": name, "args": {...}}  (or "list_tools")
"""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

CLI = r"C:\Program Files\SolidCraft\solidcraft-cli.exe"
calls = json.load(open(sys.argv[1], encoding="utf-8"))
extra = sys.argv[2:]
p = subprocess.Popen([CLI, "mcp", *extra], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, encoding="utf-8")

def send(msg):
    p.stdin.write(json.dumps(msg) + "\n"); p.stdin.flush()

def recv(id_):
    while True:
        line = p.stdout.readline()
        if not line:
            raise SystemExit("server closed: " + p.stderr.read())
        m = json.loads(line)
        if m.get("id") == id_:
            return m

send({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "cc", "version": "1"}}})
init = recv(0)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
i = 1
for c in calls:
    if c == "instructions":
        print(init["result"].get("instructions", "")); continue
    if c == "list_tools":
        send({"jsonrpc": "2.0", "id": i, "method": "tools/list"})
        r = recv(i)
        for t in r["result"]["tools"]:
            print("##", t["name"], "-", t.get("description", "")[:300])
        i += 1; continue
    send({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": c["tool"], "arguments": c.get("args", {})}})
    r = recv(i); i += 1
    print(f"=== {c['tool']}")
    if "error" in r:
        print("ERROR", json.dumps(r["error"])); continue
    for part in r["result"].get("content", []):
        if part.get("type") == "image":
            import base64
            fn = f"shot_{i}.png"; open(fn, "wb").write(base64.b64decode(part["data"])); print("saved", fn)
        if part.get("type") == "text":
            t = part["text"]
            if c["tool"] == "batch":
                try:
                    j = json.loads(t)
                    j.pop("results", None)
                    t = json.dumps(j)
                except Exception:
                    pass
            print(t)
    if r["result"].get("isError"):
        print("(isError)")
p.stdin.close()
p.wait(timeout=30)
