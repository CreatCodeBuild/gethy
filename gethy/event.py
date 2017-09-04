from gethy.state import Stream, StreamSender


class H2Event:
	pass


class RequestEvent(H2Event):

	def __init__(self, stream: Stream):
		self.stream = stream


class MoreDataToSendEvent(H2Event):

	def __init__(self, data: bytes):
		self.data = data
