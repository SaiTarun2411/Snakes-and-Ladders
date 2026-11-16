"""Exercise the real Streamlit app and independent friend sessions over its protocol."""
import asyncio
import json
import os
import uuid
from tornado.websocket import websocket_connect
from tornado.httpclient import HTTPRequest
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

BASE = os.environ.get('GAME_TEST_URL', 'http://localhost:8501').rstrip('/')
TYPES = ('tictactoe', 'dots', 'connect4', 'chess', 'snake', 'math')


class Session:
    async def open(self):
        url = BASE.replace('https://', 'wss://').replace('http://', 'ws://')+'/_stcore/stream'
        self.socket = await websocket_connect(HTTPRequest(url, headers={'Origin': BASE}, connect_timeout=20), subprotocols=['streamlit'])
        self.widget = None
        self.fragment = None
        message = BackMsg(); message.rerun_script.SetInParent()
        await self.socket.write_message(message.SerializeToString(), binary=True)
        return await self.wait(lambda data: True)

    async def wait(self, condition):
        async def read():
            while True:
                raw = await self.socket.read_message()
                if raw is None: raise AssertionError('Streamlit session closed')
                msg = ForwardMsg(); msg.ParseFromString(raw)
                if msg.HasField('auto_rerun'): self.fragment = msg.auto_rerun.fragment_id
                if msg.HasField('delta') and msg.delta.HasField('new_element'):
                    element = msg.delta.new_element
                    if element.HasField('exception'):
                        raise AssertionError(str(element.exception))
                    if element.HasField('component_instance'):
                        component = element.component_instance
                        self.widget = component.id
                        data = json.loads(component.json_args)['data']
                        if condition(data):
                            self.data = data
                            return data
        return await asyncio.wait_for(read(), 30)

    async def refresh(self, condition):
        message = BackMsg()
        message.rerun_script.fragment_id = self.fragment
        message.rerun_script.is_auto_rerun = True
        await self.socket.write_message(message.SerializeToString(), binary=True)
        return await self.wait(condition)

    async def action(self, action, **extra):
        nonce = uuid.uuid4().hex
        message = BackMsg()
        if self.fragment: message.rerun_script.fragment_id = self.fragment
        widget = message.rerun_script.widget_states.widgets.add()
        widget.id = self.widget
        widget.json_value = json.dumps(dict(action=action, nonce=nonce, **extra))
        await self.socket.write_message(message.SerializeToString(), binary=True)
        data = await self.wait(lambda d: d.get('ack') == nonce)
        assert not data['error'], (action, data['error'])
        return data

    def close(self):
        self.socket.close()


def first(g):
    return {'tictactoe':0, 'dots':'h-0-0', 'connect4':3, 'chess':'e2e4', 'math':g.get('question',{}).get('options',[None])[0]}[g['game_type']]


async def main():
    host, guest = Session(), Session()
    await host.open(); await guest.open()
    try:
        for kind in TYPES:
            data = await host.action('new', game_type=kind, mode='computer', count=2, difficulty='hard')
            assert data['game']['game_type'] == kind
            assert '_answer' not in data['game']
            if kind == 'snake':
                data = await host.action('snake_start')
                data = await host.action('snake_input', seat=0, value='down')
                assert data['game']['snakes'][0]['next'] == 'down'
            else:
                data = await host.action('arcade_move', version=0, value=first(data['game']))
                assert data['game']['turn'] == 1
                data = await host.action('arcade_move', version=data['game']['version'], computer=True)
                assert data['game']['version'] == 2
            print(kind+': local app dispatch and computer play passed')
            data = await host.action('create', game_type=kind, count=2, name='Alice')
            code = data['room']
            data = await guest.action('join', code=code, name='Bob')
            assert data['seat'] == 1
            data = await host.action('start')
            if kind == 'snake':
                data = await host.action('snake_start')
                data = await guest.action('snake_input', value='up')
                assert data['game']['snakes'][1]['next'] == 'up'
            else:
                data = await host.action('arcade_move', version=0, value=first(data['game']))
                data = await guest.refresh(lambda d: d.get('room') == code and d['game']['version'] == 1)
                assert data['game']['turn'] == 1
                data = await guest.action('arcade_move', version=1, value=(1 if kind == 'tictactoe' else 'h-0-1' if kind == 'dots' else 2 if kind == 'connect4' else 'e7e5' if kind == 'chess' else data['game']['question']['options'][0]))
                assert data['game']['version'] == 2
            print(kind+': independent friend sessions and seat controls passed')
            await host.action('home'); await guest.action('home')
    finally:
        host.close(); guest.close()


if __name__ == '__main__':
    asyncio.run(main())
