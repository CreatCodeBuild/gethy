from gethy import HTTP2Protocol
from gethy.event import RequestEvent, MoreDataToSendEvent
from gethy.http2protocol import Stream

from helpers import FrameFactory

from h2.events import WindowUpdated

p = HTTP2Protocol()


def test_receive():
	"""
	able to receive headers with no data
	"""

	headers = [
		(':method', 'GET'),
		(':path', '/'),
		(':scheme', 'https'),
		(':authority', 'example.com'),
	]

	frame_factory = FrameFactory()

	p.receive(frame_factory.preamble())

	f1 = frame_factory.build_headers_frame(headers, stream_id=1, flags=['END_STREAM'])
	data = f1.serialize()
	e = p.receive(data)

	assert len(e) == 1
	assert isinstance(e[0], RequestEvent)

	event = e[0]
	assert event.stream.stream_id == 1
	assert event.stream.headers == headers
	assert event.stream.data == b''
	assert event.stream.buffered_data is None
	assert event.stream.stream_ended is True


def test_send_headers_only():
	headers = [
		(':status', '200'),
	]

	stream = Stream(1, headers)
	stream.stream_ended = True
	stream.buffered_data = None
	stream.data = None

	events = p.send(stream)
	assert len(events) == 2
	for event in events:
		assert isinstance(event, MoreDataToSendEvent)


def test_send_headers_and_data():
	"""
	able to receive headers and small amount data.
	able to send headers and small amount of data
	"""
	headers = [
		(':method', 'POST'),
		(':path', '/'),
		(':scheme', 'https'),
		(':authority', 'example.com'),
	]

	frame_factory = FrameFactory()

	# p.receive(frame_factory.preamble())

	f1 = frame_factory.build_headers_frame(headers, stream_id=3)
	f2 = frame_factory.build_data_frame(b'1', stream_id=3, flags=['END_STREAM'], )
	data = b''.join(map(lambda f: f.serialize(), [f1, f2]))
	p.receive(data)

	headers = [
		(':status', '400'),
	]

	stream = Stream(3, headers)
	stream.stream_ended = True
	stream.buffered_data = None
	stream.data = bytes(1024*63)

	events = p.send(stream)
	assert len(events) == 10
	for event in events:
		assert isinstance(event, MoreDataToSendEvent)

	assert not p.outbound_streams
	assert not p.inbound_streams


def test_flow_control():
	"""
	test flow control by sending large data
	"""
	print("\n\n\n\n\n\n\n\n\n\n")
	headers = [
		(':method', 'GET'),
		(':path', '/'),
		(':scheme', 'https'),
		(':authority', 'example.com'),
	]

	frame_factory = FrameFactory()

	# p.receive(frame_factory.preamble())

	f = frame_factory.build_headers_frame(headers, stream_id=5)
	p.receive(f.serialize())

	headers = ((':status', '400'),)

	stream = Stream(5, headers)
	stream.stream_ended = True
	stream.buffered_data = None
	size = 1024 * 63 * 100
	stream.data = bytes(size)  # 8MB

	data_sent = 0

	events = p.send(stream)
	print(p.outbound_streams)
	if events:
		for event in events:

			if event.application_bytes_sent:
				print(event.application_bytes_sent)
				data_sent += event.application_bytes_sent
				print('data_send::', data_sent)
			assert isinstance(event, MoreDataToSendEvent)


	while data_sent < size:
		print('<<<<<<<<<<<<<<<<<<<<<<<', data_sent, size)

		f = frame_factory.build_window_update_frame(0, 30000)
		events = p.receive(f.serialize())
		f = frame_factory.build_window_update_frame(5, 30000)
		events.extend(p.receive(f.serialize()))
		print("p.receive")

		print("events", events)
		for event in events:

			if event.application_bytes_sent:
				data_sent += event.application_bytes_sent
				print('data_send:', data_sent)
			assert isinstance(event, MoreDataToSendEvent)

	print('data_sent ---', data_sent)
	diff = data_sent - size
	assert diff == 0
