import socket
import sys
import json
import threading
import time
import os
from pathlib import Path

class OverlayNode:
    def __init__(self, host, port, neighbors=None):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.node_id = f"{host}:{port}"
        self.db_path = self.setup_database()
        self.neighbors = self.load_neighbors() if not neighbors else self.save_neighbors(neighbors)
        self.active = True
        self.received_messages = set()

    def setup_database(self):
        """Configura a pasta database e retorna o caminho do arquivo de vizinhos"""
        # Criar pasta database se não existir
        home = str(Path.home())
        curren_dir= Path.cwd()
        parent_dir = curren_dir.parent
        db_dir = parent_dir / "database"
        db_dir.mkdir(exist_ok=True)
        return db_dir / f"neighbors_{self.node_id.replace(':', '_')}.json"

    def load_neighbors(self):
        """Carrega vizinhos do arquivo de database"""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    print(f"Vizinhos carregados do arquivo: {data['neighbors']}")
                    return data['neighbors']
        except Exception as e:
            print(f"Erro ao carregar vizinhos: {e}")
        return []

    def save_neighbors(self, neighbors):
        """Salva vizinhos no arquivo de database"""
        try:
            with open(self.db_path, 'w') as f:
                json.dump({'neighbors': neighbors}, f, indent=2)
            print(f"Vizinhos salvos no arquivo: {neighbors}")
            return neighbors
        except Exception as e:
            print(f"Erro ao salvar vizinhos: {e}")
            return []

    def add_neighbor(self, neighbor):
        """Adiciona um novo vizinho e atualiza o arquivo"""
        if neighbor not in self.neighbors:
            self.neighbors.append(neighbor)
            self.save_neighbors(self.neighbors)
            print(f"Novo vizinho adicionado: {neighbor}")

    def remove_neighbor(self, neighbor):
        """Remove um vizinho e atualiza o arquivo"""
        if neighbor in self.neighbors:
            self.neighbors.remove(neighbor)
            self.save_neighbors(self.neighbors)
            print(f"Vizinho removido: {neighbor}")

    def start(self):
        # Iniciar thread para receber mensagens
        receive_thread = threading.Thread(target=self.receive_messages)
        receive_thread.daemon = True
        receive_thread.start()

        # Enviar HELLO inicial para todos os vizinhos
        self.send_hello_to_neighbors()

        while True:
            try:
                self.process_command(input("""
Comandos disponíveis:
- 'neighbors': listar vizinhos
- 'add <host:port>': adicionar vizinho
- 'remove <host:port>': remover vizinho
- 'quit': sair
Comando: """))
            except KeyboardInterrupt:
                self.active = False
                break

    def process_command(self, command):
        """Processa comandos do usuário"""
        parts = command.strip().split()
        if not parts:
            return

        cmd = parts[0].lower()
        if cmd == 'quit':
            self.active = False
        elif cmd == 'neighbors':
            print(f"Vizinhos ativos: {self.neighbors}")
        elif cmd == 'add' and len(parts) == 2:
            self.add_neighbor(parts[1])
            self.send_hello_to_neighbors()
        elif cmd == 'remove' and len(parts) == 2:
            self.remove_neighbor(parts[1])
        else:
            print("Comando inválido")

    def send_hello_to_neighbors(self):
        hello_msg = {
            "type": "HELLO",
            "source": self.node_id,
            "timestamp": time.time()
        }
        self.broadcast_to_neighbors(hello_msg)

    def broadcast_to_neighbors(self, message):
        message_str = json.dumps(message)
        for neighbor in self.neighbors:
            try:
                host, port = neighbor.split(':')
                self.socket.sendto(message_str.encode(), (host, int(port)))
            except Exception as e:
                print(f"Erro ao enviar para {neighbor}: {e}")

    def receive_messages(self):
        while self.active:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode())
                
                # Verificar se já recebemos esta mensagem
                msg_id = f"{message.get('source')}_{message.get('timestamp')}"
                if msg_id in self.received_messages:
                    continue
                
                self.received_messages.add(msg_id)
                
                # Processar mensagem recebida
                if message["type"] == "HELLO":
                    print(f"Recebi HELLO de {message['source']}")
                    # Responder com HELLO se não for uma mensagem nossa
                    if message['source'] != self.node_id:
                        self.send_hello_to_neighbors()
                
            except Exception as e:
                if self.active:
                    print(f"Erro ao receber mensagem: {e}")

    def cleanup(self):
        self.active = False
        self.socket.close()

def main():
    if len(sys.argv) < 3:
        print("Uso: python oNode.py <host> <port> [neighbor1_host:port] [neighbor2_host:port] ...")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    neighbors = sys.argv[3:] if len(sys.argv) > 3 else []

    node = OverlayNode(host, port, neighbors)
    try:
        node.start()
    finally:
        node.cleanup()

if __name__ == "__main__":
    main()