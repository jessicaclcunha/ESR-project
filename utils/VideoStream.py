class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		
	def nextFrame(self):
		"""Get next frame."""
		try:
			# Attempt to read the frame length for custom format
			data = self.file.read(5)
			if data:
				try:
					framelength = int(data)
					# If successfully read, assume it's a custom format
					data = self.file.read(framelength)
					self.frameNum += 1
					return data
				except ValueError:
					# If frame length is invalid, fall back to standard Mjpeg logic
					pass
			
			# Standard Mjpeg logic (search for JPEG end marker)
			frame_data = bytearray(data)  # Start with the first 5 bytes already read
			while True:
				byte = self.file.read(1)
				if not byte:
					break
				frame_data.append(byte[0])
				if len(frame_data) > 2 and frame_data[-2:] == b'\xff\xd9':  # JPEG end marker
					self.frameNum += 1
					break
			return bytes(frame_data) if frame_data else None
		except Exception as e:
			raise IOError(f"Error reading frame: {e}")

			
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	
