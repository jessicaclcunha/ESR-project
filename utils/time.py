import time
from datetime import datetime

NODE_PING_INTERVAL = 3
NODE_RESPONSE_WARNING = 5
NODE_RESPONSE_TIMEOUT = 10
CLIENT_NO_POP_WAIT_TIME = 5
NODE_NO_NEIGHBOUR_WAIT_TIME = 5
BEST_NEIGHBOUR_REQUEST_INTERVAL = 10
NODE_ROUTING_TABLE_MONITORING_INTERVAL = 3

def formattedTime() -> str:
	"""
	Função que devolve uma string com o tempo atual no formato 'YYYY-MM-DD HH:MM:SS'. 
	"""
	return datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

def nodePastTimeout(nodeLastestTimestamp: float) -> str:
	"""
	Função que verifica se o tempo de resposta do node ultrapassou o limite.

	:returns: "OK", "WARN" ou "NOTACTIVE".
	"""
	timeDiff = time.time() - nodeLastestTimestamp

	if timeDiff < NODE_RESPONSE_WARNING:
		return "OK"
	elif timeDiff < NODE_RESPONSE_TIMEOUT:
		return "WARN"
	else:
		return "NOTACTIVE"
