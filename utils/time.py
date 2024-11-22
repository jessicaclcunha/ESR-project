import time
from datetime import datetime

NODE_RESPONSE_TIMEOUT = 10
NODE_RESPONSE_WARNING = 5

def formattedTime() -> str:
	"""
	Função que devolve uma string com o tempo atual no formato 'YYYY-MM-DD HH:MM:SS'. 
	"""
	return datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

def nodePastTimeout(nodeTime: float) -> bool:
	"""
	Função que verifica se o tempo de resposta do node ultrapassou o limite.
	"""
	return time.time() - nodeTime > NODE_RESPONSE_TIMEOUT
