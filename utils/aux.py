import time
import random

def medir_atraso(sock, destino):
    inicio = time.time()
    sock.sendto(b'ping', destino)
    resposta, _ = sock.recvfrom(1024)
    fim = time.time()
    rtt = fim - inicio
    return rtt