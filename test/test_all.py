from gethy import HTTP2Protocol
from gethy.event import RequestEvent, MoreDataToSendEvent
from gethy.http2protocol import Stream

from helpers import FrameFactory

# 因为我们的测试很少，所以全局变量也OK
frame_factory = FrameFactory()
protocol = HTTP2Protocol()
protocol.receive(frame_factory.preamble())  # h2 建立连接时必要的字段
headers = [
	(':method', 'GET'),
	(':path', '/'),
	(':scheme', 'https'),
	(':authority', 'example.com'),
]


def test_receive_headers_only():
	"""
	able to receive headers with no data
	"""
	# 客户端发起的 session 的 stream id 是单数
	# 服务器发起的 session 的 stream id 是双数
	# 一个 session 包含一对 request/response
	# id 0 代表整个 connection
	stream_id = 1

	# 在这里手动生成一个 client 的 request frame，来模拟客户端请求
	frame_from_client = frame_factory.build_headers_frame(headers, stream_id=stream_id, flags=['END_STREAM'])

	data = frame_from_client.serialize()  # 将数据结构序列化为 TCP 可接受的 bytes
	events = protocol.receive(data)       # 服务器端接收请求，得到一些 gethy 定义的事件

	# 因为请求只有一个请求，所以仅可能有一个事件，且为 RequestEvent 事件
	assert len(events) == 1
	assert isinstance(events[0], RequestEvent)

	event = events[0]
	assert event.stream.stream_id == stream_id
	assert event.stream.headers == headers     # 验证 Headers
	assert event.stream.data == b''            # 验证没有任何数据
	assert event.stream.buffered_data is None  # 验证没有任何数据
	assert event.stream.stream_ended is True   # 验证请求完整（Stream 结束）


def test_receive_headers_and_data():
	stream_id = 3

	client_headers_frame = frame_factory.build_headers_frame(headers, stream_id=stream_id)
	headers_bytes = client_headers_frame.serialize()

	data = b'some amount of data'
	client_data_frame = frame_factory.build_data_frame(data, stream_id=stream_id, flags=['END_STREAM'])
	data_bytes = client_data_frame.serialize()

	events = protocol.receive(headers_bytes+data_bytes)

	assert len(events) == 1
	assert isinstance(events[0], RequestEvent)

	event = events[0]
	assert event.stream.stream_id == stream_id
	assert event.stream.headers == headers     # 验证 Headers
	assert event.stream.data == data           # 验证没有任何数据
	assert event.stream.buffered_data is None  # 验证没有任何数据
	assert event.stream.stream_ended is True   # 验证请求完整（Stream 结束）


def test_send_headers_only():
	stream_id = 1
	response_headers = [(':status', '200')]

	stream = Stream(stream_id, response_headers)
	stream.stream_ended = True
	stream.buffered_data = None
	stream.data = None

	events = protocol.send(stream)
	assert len(events) == 2
	for event in events:
		assert isinstance(event, MoreDataToSendEvent)


def test_send_headers_and_data():
	"""
	able to receive headers and small amount data.
	able to send headers and small amount of data
	"""
	stream_id = 3
	response_headers = [(':status', '400')]
	size = 1024 * 64 - 2  # default flow control window size per stream is 64 KB - 1 byte

	stream = Stream(stream_id, response_headers)
	stream.stream_ended = True
	stream.buffered_data = None
	stream.data = bytes(size)

	events = protocol.send(stream)
	assert len(events) == size // protocol.block_size + 3
	for event in events:
		assert isinstance(event, MoreDataToSendEvent)

	assert not protocol.outbound_streams
	assert not protocol.inbound_streams


def test_flow_control():
	"""
	test flow control by sending large data
	"""
	stream_id = 5
	f = frame_factory.build_headers_frame(headers, stream_id=5)
	protocol.receive(f.serialize())

	response_headers = ((':status', '400'),)

	stream = Stream(stream_id, response_headers)
	stream.stream_ended = True
	stream.buffered_data = None
	size = 1024 * 63 * 100
	stream.data = bytes(size)  # 8MB

	data_sent = 0

	events = protocol.send(stream)

	if events:
		for event in events:

			if event.application_bytes_sent:
				print(event.application_bytes_sent)
				data_sent += event.application_bytes_sent

			assert isinstance(event, MoreDataToSendEvent)

	while data_sent < size:

		f = frame_factory.build_window_update_frame(0, 30000)  # update per connection flow control window
		events = protocol.receive(f.serialize())
		f = frame_factory.build_window_update_frame(stream_id, 30000)
		events.extend(protocol.receive(f.serialize()))

		for event in events:

			if event.application_bytes_sent:
				data_sent += event.application_bytes_sent

			assert isinstance(event, MoreDataToSendEvent)

	diff = data_sent - size
	assert diff == 0
