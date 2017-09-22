import logging

import h2.config
import h2.connection
import h2.events
import h2.exceptions
from h2.events import (
	RequestReceived,
	DataReceived,
	WindowUpdated,
	StreamEnded
)

from .event import RequestEvent, MoreDataToSendEvent


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
			assert isinstance(instance.data, type(None)) or isinstance(instance.data, bytes)
		else:
			assert instance.data is None
			assert isinstance(instance.buffered_data, list)


class StreamSender:
	"""
	"""

	def __init__(self, stream: Stream, connection: h2.connection):
		print("StreamSender.__init__", stream.stream_id, stream.stream_ended)
		Stream.value_check(stream)

		self.stream = stream
		self.is_waiting_for_flow_control = False
		self.headers_sent = False
		self.done = False  # done StreamSender should be removed from State.outbound_streams

		self.i = 0  # data sent index
		self.connection = connection

	def send(self, read_chunk_size):

		data_to_send_events = []

		stream = self.stream

		print("StreamSender.send", stream.stream_id)

		if not self.headers_sent:
			print("This Line Should Only Be Print Once Per Stream ID", stream.stream_id)
			self.done = not stream.data

			print("StreamSender", stream.stream_id, stream.headers, "end", self.done)

			self.connection.send_headers(stream.stream_id, stream.headers, end_stream=self.done)
			self.headers_sent = True

			data_to_send_events.append(MoreDataToSendEvent(self.connection.data_to_send(), None))

			self.done = not self.stream.data

		# send http body/data
		while not self.done:

			while not self.connection.local_flow_control_window(stream.stream_id):
				print('control window', self.connection.local_flow_control_window(stream.stream_id))
				self.is_waiting_for_flow_control = True
				print("StreamSender:: waiting for flow control %s sent" % self.i)
				return data_to_send_events

			chunk_size = min(self.connection.local_flow_control_window(stream.stream_id), read_chunk_size)

			data_to_send = stream.data[self.i: self.i+chunk_size]
			self.done = (len(data_to_send) != chunk_size)

			self.connection.send_data(stream.stream_id, data_to_send, end_stream=self.done)
			print("///////////", self.i, len(data_to_send))
			data_to_send_events.append(MoreDataToSendEvent(self.connection.data_to_send(), len(data_to_send)))

			self.i += len(data_to_send)

		data_to_send_events.append(MoreDataToSendEvent(self.connection.data_to_send(), None))
		return data_to_send_events


class HTTP2Protocol:
	"""
	A pure in-memory H2 implementation for application level development.
	
	It does not do IO.

	:property inbound_streams: a dictionary of streams received from the client. {stream_id: Stream}
	:property flow_control_events: a list of stream ids which are flow controlled
	:property outbound_streams: a dictionary of StreamSender-s. {stream_id: StreamSender}
	"""
	def __init__(self):
		self.current_events = []

		self.inbound_streams = {}
		# stream ids which are waiting for flow control
		self.flow_control_events = []
		self.outbound_streams = {}

		config = h2.config.H2Configuration(client_side=False, header_encoding='utf-8')
		self.http2_connection = h2.connection.H2Connection(config=config)

	def receive(self, data: bytes):
		"""
		receive bytes, return HTTP Request object if any stream is ready
		else return None
		
		:param data: bytes, received from a socket
		:return: list, of Request
		"""

		logging.debug("HTTP2Protocol receive begin")

		# First, proceed incoming data
		# handle any events emitted from h2
		events = self.http2_connection.receive_data(data)
		for event in events:
			self.handle_event(event)

		self.inbound()
		self.outbound()

		events = self.current_events	# assign all current events to an events variable and return this variable
		self.current_events = []		# empty current event list by assign a newly allocated list

		logging.debug("HTTP2Protocol receive return")
		return events

	def send(self, stream: Stream):
		"""
		Prepare TCP/Socket level data to send. This function does not do IO.

		Create a StreamSender and add it to outbound cache
		
		:param stream: a HTTP2 stream
		:return: bytes which is to send to socket 
		"""
		print('------------------------------send %s-----------------------------------' % stream.stream_id)
		self.outbound_streams[stream.stream_id] = StreamSender(stream, self.http2_connection)

		self.inbound()
		self.outbound()

		events = self.current_events	# assign all current events to an events variable and return this variable
		self.current_events = []		# empty current event list by assign a newly allocated list
		print('------------------------------send end---------------------------------')
		return events

	def inbound(self):
		"""
		exercise all inbound streams
		"""
		print("--------------intbound-------------------")
		# This is a list of stream ids
		stream_to_delete_from_inbound_cache = []

		# inbound_streams is a dictionary with schema {stream_id: stream_obj}
		# therefore use .values()
		for stream in self.inbound_streams.values():

			logging.debug("HTTP2Protocol.receive check inbound_streams")

			if stream.stream_ended:
				logging.debug("HTTP2Protocol.receive %s %s", stream.stream_id, stream.stream_ended)

				# create a HTTP Request event, add it to current event list
				event = RequestEvent(stream)
				self.current_events.append(event)

				# Emitting an event means to clear the cached inbound data
				# The caller has to handle all returned events. Otherwise bad
				stream_to_delete_from_inbound_cache.append(stream.stream_id)

		# clear the inbound cache
		for stream_id in stream_to_delete_from_inbound_cache:
			del self.inbound_streams[stream_id]
		print("--------------inbound end---------------")

	def outbound(self):
		"""
		exercise all out bound stream senders
		"""
		print("--------------outbound %s-----------------" % list(self.outbound_streams.keys()))
		stream_sender_to_delete_from_outbound_cache = []

		for stream_id, stream_sender in self.outbound_streams.items():
			print("%s in self.outbound_streams.values()" % stream_id)

			if not stream_sender.is_waiting_for_flow_control:

				print("HTTP2Protocol.receive", stream_id)

				events = stream_sender.send(8096)

				self.current_events.extend(events)

				if stream_sender.done:
					stream_sender_to_delete_from_outbound_cache.append(stream_id)

				if stream_sender.is_waiting_for_flow_control:
					self.flow_control_events.append(stream_id)

		# clear outbound cache
		for stream_id in stream_sender_to_delete_from_outbound_cache:
			del self.outbound_streams[stream_id]
		print("--------------outbound end---------------")

	def handle_event(self, event: h2.events.Event):
		print("HTTP2Protocol.handle_event", type(event))
		if isinstance(event, h2.events.RequestReceived):
			self.request_received(event)

		elif isinstance(event, h2.events.DataReceived):
			self.data_received(event)

		elif isinstance(event, h2.events.WindowUpdated):
			self.window_updated(event)

		else:
			print("Has not implement ", type(event), " handler")

	def request_received(self, event: RequestReceived):
		self.inbound_streams[event.stream_id] = Stream(event.stream_id, event.headers)

		if event.priority_updated:
			print("RequestReceived.priority_updated is not implemented")

		if event.stream_ended:
			self.stream_ended(event.stream_ended)

		Stream.value_check(self.inbound_streams[event.stream_id])  # debug

	def data_received(self, event: DataReceived):
		self.inbound_streams[event.stream_id].buffered_data.append(event.data)

		if event.flow_controlled_length:
			print("DataReceived.flow_controlled_length is not implemented")
			print(event.flow_controlled_length)

		if event.stream_ended:
			self.stream_ended(event.stream_ended)

		Stream.value_check(self.inbound_streams[event.stream_id])  # debug

	def window_updated(self, event: WindowUpdated):
		stream_id = event.stream_id

		print("-----------------window_updated", stream_id, event.delta)

		print("-----------------flow control events", self.flow_control_events)

		if stream_id and stream_id in self.flow_control_events:
			print("window_updated: stream_id in state.flow_control_events")
			self.flow_control_events.remove(stream_id)
			print('----------------self.outbound_streams', self.outbound_streams)
			stream_sender = self.outbound_streams[stream_id]
			stream_sender.is_waiting_for_flow_control = False

		elif not stream_id:
			print("window_updated stream_id is", stream_id)
			# Need to keep a real list here to use only the events present at
			# this time.
			blocked_streams = self.flow_control_events
			for stream_id in blocked_streams:
				print("window_updated blocked streams", blocked_streams)
				stream_sender = self.outbound_streams[stream_id]
				stream_sender.is_waiting_for_flow_control = False
				self.flow_control_events = []

	def stream_ended(self, event: StreamEnded):
		stream = self.inbound_streams[event.stream_id]
		stream.stream_ended = True
		stream.data = b''.join(stream.buffered_data)
		stream.buffered_data = None
		Stream.value_check(stream)  # debug




