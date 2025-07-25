from time import time
HEADER_SIZE = 12

class RtpPacket:	
	def __init__(self):
		self.header = bytearray(HEADER_SIZE)
		
	def encode(self, version, padding, extension, cc, seqnum, marker, pt, ssrc, payload, video_id = ""):
		"""Encode the RTP packet with header fields and payload."""
		timestamp = int(time())
		self.header[0] = (self.header[0] | version << 6) & 0xC0; # 2 bits
		self.header[0] = (self.header[0] | padding << 5); # 1 bit
		self.header[0] = (self.header[0] | extension << 4); # 1 bit
		self.header[0] = (self.header[0] | (cc & 0x0F)); # 4 bits
		self.header[1] = (self.header[1] | marker << 7); # 1 bit
		self.header[1] = (self.header[1] | (pt & 0x7f)); # 7 bits
		self.header[2] = (seqnum >> 8); 
		self.header[3] = (seqnum & 0xFF);
		self.header[4] = (timestamp >> 24);
		self.header[5] = (timestamp >> 16) & 0xFF;
		self.header[6] = (timestamp >> 8) & 0xFF;
		self.header[7] = (timestamp & 0xFF);
		self.header[8] = (ssrc >> 24);
		self.header[9] = (ssrc >> 16) & 0xFF;
		self.header[10] = (ssrc >> 8) & 0xFF;
		self.header[11] = ssrc & 0xFF
		modified_payload = video_id.encode('utf-8') + b'\n' + payload
		self.payload = modified_payload
		
	def decode(self, byteStream):
		"""Decode the RTP packet."""
		self.header = bytearray(byteStream[:HEADER_SIZE])
		self.payload = byteStream[HEADER_SIZE:]
	
	def version(self):
		"""Return RTP version."""
		return int(self.header[0] >> 6)
	
	def seqNum(self):
		"""Return sequence (frame) number."""
		seqNum = self.header[2] << 8 | self.header[3]
		return int(seqNum)
	
	def timestamp(self):
		"""Return timestamp."""
		timestamp = self.header[4] << 24 | self.header[5] << 16 | self.header[6] << 8 | self.header[7]
		return int(timestamp)
	
	def payloadType(self):
		"""Return payload type."""
		pt = self.header[1] & 127
		return int(pt)
	
	def getPayload(self):
		"""Return payload."""
		try:
			payload = self.payload.split(b'\n',1)[1]
			if not payload.endswith(b'\xFF\xD9'):
				payload += b'\xFF\xD9'
			return payload
		except IndexError:
			return self.payload

	def getVideoId(self):
		"""Return video id."""
		return self.payload.split(b'\n',1)[0].decode('utf-8')
		
	def getPacket(self):
		"""Return RTP packet."""
		return self.header + self.payload

	def printheader(self):
		print("[RTP Packet] Version: ...")
