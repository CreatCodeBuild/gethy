class H2Event:
	pass


class RequestEvent(H2Event):

	def __init__(self, stream):
		self.stream = stream


class MoreDataToSendEvent(H2Event):

	def __init__(self, data: bytes, bytes_sent: int):
		self.data = data  # to send over TCP socket
		self.bytes_sent = bytes_sent  # HTTP level bytes sent
