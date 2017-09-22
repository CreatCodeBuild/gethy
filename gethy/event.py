class H2Event:
	pass


class RequestEvent(H2Event):

	def __init__(self, stream):
		self.stream = stream


class MoreDataToSendEvent(H2Event):

	def __init__(self, data: bytes, application_bytes_sent: int or None):
		"""
		:param data: send over TCO socket
		:param application_bytes_sent:
			the number of application level bytes which 'data' contains
			None if not stream data
		"""
		self.data = data
		self.application_bytes_sent = application_bytes_sent
