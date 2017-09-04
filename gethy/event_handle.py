"""
Handles h2 event
"""

from h2.events import \
	RequestReceived, \
	DataReceived, \
	WindowUpdated, \
	StreamEnded

from .state import State, Stream


def request_received(event: RequestReceived, state: State):
	state.inbound_streams[event.stream_id] = Stream(event.stream_id, event.headers)

	if event.priority_updated:
		print("RequestReceived.priority_updated is not implemented")

	if event.stream_ended:
		stream_ended(event.stream_ended, state)

	Stream.value_check(state.inbound_streams[event.stream_id])  # debug

def data_received(event: DataReceived, state: State):
	state.inbound_streams[event.stream_id].buffered_data.append(event.data)

	if event.flow_controlled_length:
		print("DataReceived.flow_controlled_length is not implemented")
		print(event.flow_controlled_length)

	if event.stream_ended:
		stream_ended(event.stream_ended, state)

	Stream.value_check(state.inbound_streams[event.stream_id])  # debug

def window_updated(event: WindowUpdated, state: State):
	stream_id = event.stream_id

	print("window_updated", stream_id, event.delta)

	if stream_id and stream_id in state.flow_control_events:
		print("window_updated: stream_id in state.flow_control_events")
		stream_id = state.flow_control_events.pop(stream_id)
		stream_sender = state.outbound_streams[stream_id]
		stream_sender.is_waiting_for_flow_control = False

	elif not stream_id:
		print("window_updated stream_id is", stream_id)
		# Need to keep a real list here to use only the events present at
		# this time.
		blocked_streams = state.flow_control_events
		for stream_id in blocked_streams:
			print("window_updated blocked streams", blocked_streams)
			stream_sender = state.outbound_streams[stream_id]
			stream_sender.is_waiting_for_flow_control = False
			state.flow_control_events = []


def stream_ended(event: StreamEnded, state: State):
	stream = state.inbound_streams[event.stream_id]
	stream.stream_ended = True
	stream.data = b''.join(stream.buffered_data)
	stream.buffered_data = None
	Stream.value_check(stream)  # debug
