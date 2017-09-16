from gethy import HTTP2Protocol
from gethy.event import RequestEvent
from gethy.state import Stream

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


def test_send():

	headers = [
		(':status', '200'),
		('content-length', '0')
	]

	stream = Stream(1, headers)
	stream.stream_ended = True
	stream.buffered_data = None
	stream.data = b''

	e = p.send(stream)

	# assert len(e) == 1
	# assert isinstance(e[0], RequestEvent)
