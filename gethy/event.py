class H2Event:
	pass


class RequestEvent(H2Event):

	def __init__(self, stream):
		self.stream = stream


class MoreDataToSendEvent(H2Event):

	def __init__(self, data: bytes):
		self.data = data
