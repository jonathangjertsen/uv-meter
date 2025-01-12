import network
import time
import socket

print("read config.txt")
with open("config.txt") as f:
    id = f.readline()
    ssid = f.readline()
    key = f.readline()
    server = f.readline()
    port = int(f.readline())

print("connect to network")
NET = network.WLAN(network.WLAN.IF_STA)
if not NET.isconnected():
    print("connecting to network")
    NET.active(True)
    NET.connect(ssid, key)
    while not NET.connected():
        print("failed to connect. retry in 1s")
        time.sleep(1)

print("getting addrinfo")
SOCKADDR = socket.getaddrinfo(server, port)[0][-1]

print("connecting: ", server)
s = socket.socket()
s.connect(SOCKADDR)
s.send(f"GET /config/{port}")
while True:
    data = s.recv(4096)
    if data:
        break
    else:
        s.close()
        raise Exception("no data")
s.close()
print(data)
