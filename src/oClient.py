import socket
import sys

if __name__ == '__main__':
    name = socket.gethostname()
    
    if len(sys.argv) < 2:
        print('Usage: python3 oClient.py <video>')
        sys.exit(1)
    
    video = sys.argv[1]
    ip = socket.gethostbyname(name)