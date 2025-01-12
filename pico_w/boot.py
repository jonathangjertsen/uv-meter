import machine
import network
import time
import socket
import struct

BUFSIZ = 4096

class Net:
    def __init__(self, f):
        self.id = f.readline().strip()
        self.ssid = f.readline().strip()
        self.key = f.readline().strip()
        self.server = f.readline().strip()
        self.port = int(f.readline().strip())

        self.sockaddr = socket.getaddrinfo(self.server, self.port)[0][-1]
        
    def get(self, url):
        s = socket.socket()
        s.connect(self.sockaddr)
        s.send(f"GET {url} HTTP/1.1\r\nHost: {self.server}\r\n\r\n".encode('ascii'))
        data = s.recv(BUFSIZ)
        s.close()
        return data
    
    def post(self, url, buf):
        s = socket.socket()
        s.connect(self.sockaddr)
        s.send(f"POST {url} HTTP/1.1\r\nHost: {self.server}\r\nContent-Type: octet-stream\r\nContent-Length: {len(buf)}\r\n\r\n".encode('ascii') + buf)
        data = s.recv(BUFSIZ)
        s.close()
        return data
    
    def connect_wifi(self):
        iface = network.WLAN(network.WLAN.IF_STA)
        if not iface.isconnected():
            iface.active(True)
            iface.connect(self.ssid, self.key)
            while not iface.isconnected():
                time.sleep(1)

    def get_sampler(self, adc):
        return Sampler(self.get(f"/config/{self.id}"), adc)

    def send_point(self, p):
        buf = struct.pack(">H", p)
        self.post(f"/point/{self.id}", buf)
    
    def send_burst(self, burst):
        buf = bytearray()
        for p in burst:
            buf.extend(struct.pack(">H", p))
        self.post(f"/burst/{self.id}", buf)

class Sampler:
    def __init__(self, buf, adc):
        # parse body
        fields = struct.unpack_from('>IIIIIIIII', buf, buf.index(b'\r\n\r\n') + 4)
       
        self.point_n_avg = clamp(fields[0], 1, BUFSIZ/4)
        self.point_delay_us = clamp(fields[1], 0, 60_000_000)
        self.point_interval_ms = clamp(fields[2], 0, 3_600_000)
        # fields[3] reserved
        self.burst_n = clamp(fields[4], 1, BUFSIZ/4)
        self.burst_delay_us = clamp(fields[5], 0, 6_000_000)
        self.burst_interval_ms = clamp(fields[6], 0, 3_600_000)
        self.burst_n_avg = clamp(fields[7], 1, BUFSIZ/4)
        self.expiration_s = clamp(fields[8], 0, 3600)

        self.time = time.time()
        self.adc = adc

    def expired(self):
        return time.time() - self.time > self.expiration_s

    def read_once(self):
        return self.adc.read_u16()

    def read_sample_buf(self, n, delay_us):
        sbuf = []
        for _ in range(n):
            t0 = time.ticks_us()
            sbuf.append(self.read_once())
            while time.ticks_us() - t0 < delay_us:
                pass
        return sbuf

    def read_point(self):
        tot = 0
        for s in self.read_sample_buf(self.point_n_avg, self.point_delay_us):
            tot += s
        return (tot + (self.point_n_avg >> 1)) // self.point_n_avg
    
    def read_burst(self):
        pbuf = []
        for _ in range(self.burst_n):
            t0 = time.ticks_us()
            pbuf.append(self.read_point())
            while time.ticks_us() - t0 < self.burst_delay_us:
                pass
        return pbuf
    
def clamp(x, lo, hi):
    if x > hi:
        return hi
    if x < lo:
        return lo
    return x

print("init adc")
ADC = machine.ADC(28)

print("init net")
with open("config.txt") as f:
    net = Net(f)
net.connect_wifi()

print("init sampler")
sampler = net.get_sampler(ADC)
print(sampler.expiration_s)

net.send_point(sampler.read_point())
net.send_burst(sampler.read_burst())

