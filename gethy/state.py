import h2.connection


class Stream:
	"""
	"""

	def __init__(self, stream_id: int, headers: tuple):
		self.stream_id = stream_id
		self.headers = headers  # as the name indicates

		# when stream_ended is True
		# buffered_data has to be None
		# and data has to be a bytes
		#
		# if buffered_data is empty
		# then both buffered_data and data have to be None when stream_ended is True
		#
		# should write a value enforcement contract decorator for it
		self.stream_ended = False
		self.buffered_data = []
		self.data = None

	@staticmethod
	def value_check(instance):
		if instance.stream_ended:
			assert instance.buffered_data is None
			assert isinstance(instance.data, bytes)
		else:
			assert instance.data is None
			assert isinstance(instance.buffered_data, list)


class State:
	"""
	:property inbound_streams: a dictionary of streams received from the client. {stream_id: Stream}
	:property flow_control_events: a list of stream ids which are flow controlled
	:property outbound_streams: a dictionary of StreamSender-s. {stream_id: StreamSender}
	"""
	def __init__(self):
		self.inbound_streams = {}
		# stream ids which are waiting for flow control
		self.flow_control_events = []
		self.outbound_streams = {}


class StreamSender:
	"""
	"""

	def __init__(self, stream: Stream, connection: h2.connection):
		print("StreamSender.__init__", stream.stream_id, stream.stream_ended, stream.buffered_data, stream.data)
		Stream.value_check(stream)

		self.stream = stream
		self.is_waiting_for_flow_control = False
		self.headers_sent = False
		self.done = False  # done StreamSender should be removed from State.outbound_streams

		self.i = 0  # data sent index
		self.connection = connection

		self.data_to_send = []

	def send(self, read_chunk_size):

		stream = self.stream

		print("StreamSender.send", stream.stream_id)

		if not self.headers_sent:
			print("This Line Should Only Be Print Once Per Stream ID", stream.stream_id)
			self.done = not stream.data

			print("StreamSender", stream.stream_id, stream.headers, "end", self.done)

			self.connection.send_headers(stream.stream_id, stream.headers, end_stream=self.done)
			self.headers_sent = True

			self.data_to_send.append(self.connection.data_to_send())

		# send http body/data
		while True:

			while not self.connection.local_flow_control_window(stream.stream_id):
				self.is_waiting_for_flow_control = True
				return

			chunk_size = min(self.connection.local_flow_control_window(stream.stream_id), read_chunk_size)

			data_to_send = stream.data[self.i: self.i+chunk_size]
			self.done = (len(data_to_send) != chunk_size)

			self.connection.send_data(stream.stream_id, data_to_send, end_stream=self.done)
			self.data_to_send.append(self.connection.data_to_send())

			if self.done:
				break
			self.i += chunk_size

		self.data_to_send.append(self.connection.data_to_send())
