import time
from datetime import datetime


def formattedTime() -> str:
	"""
	Função que devolve uma string com o tempo atual no formato 'YYYY-MM-DD HH:MM:SS'. 
	"""
	return datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
