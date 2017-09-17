from gethy import HTTP2Protocol
from gethy.event import RequestEvent
from gethy.http2protocol import Stream

from helpers import FrameFactory


p = HTTP2Protocol()


def test_receive():

	headers = [
		(':method', 'POST'),
		(':path',   '/'),
		(':scheme', 'https'),
		(':authority', 'example.com'),
	]

	frame_factory = FrameFactory()

	p.receive(frame_factory.preamble())

	f1 = frame_factory.build_headers_frame(headers, stream_id=1)
	f2 = frame_factory.build_data_frame(b'1', stream_id=1, flags=['END_STREAM'],)
	data = b''.join(map(lambda f: f.serialize(), [f1, f2]))
	e = p.receive(data)

	assert len(e) == 1
	assert isinstance(e[0], RequestEvent)

	event = e[0]
	assert event.stream.stream_id == 1
	assert event.stream.headers == headers
	assert event.stream.data == b'1'
	assert event.stream.buffered_data is None
	assert event.stream.stream_ended is True


def test_send_headers_only():

	headers = [
		(':status', '200'),
		('content-length', '0')
	]

	stream = Stream(1, headers)
	stream.stream_ended = True
	stream.buffered_data = None
	stream.data = b'0'

	e = p.send(stream)
	print(e)
	for ev in e:
		print(ev.data)
	# assert len(e) == 1
	# assert isinstance(e[0], RequestEvent)


def test_send_headers_and_data():

	headers = [
		(':method', 'POST'),
		(':path',   '/'),
		(':scheme', 'https'),
		(':authority', 'example.com'),
	]

	frame_factory = FrameFactory()

	# p.receive(frame_factory.preamble())

	f1 = frame_factory.build_headers_frame(headers, stream_id=3)
	f2 = frame_factory.build_data_frame(b'1', stream_id=3, flags=['END_STREAM'],)
	data = b''.join(map(lambda f: f.serialize(), [f1, f2]))
	e = p.receive(data)


def test_f():
	headers = [
		(':status', '200'),
		('content-length', '1'),
	]

	stream = Stream(3, headers)
	stream.stream_ended = True
	stream.buffered_data = None
	stream.data = b'1'

	e = p.send(stream)

	# assert len(e) == 1
	# assert isinstance(e[0], RequestEvent)
