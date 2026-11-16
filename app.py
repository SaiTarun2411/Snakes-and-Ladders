"""Snakes and Ladders: Python rules with an animated Streamlit component."""
from pathlib import Path
import secrets
import time

import streamlit as st
import streamlit.components.v1 as components

from board import board_svg
from game import GameError, RoomStore, new_game, play_turn
from arcade import TYPES, snake_tick

ROOT = Path(__file__).parent
ui = components.declare_component('snakes_ladders', path=str(ROOT / 'static'))


@st.cache_resource
def rooms():
    return RoomStore()


@st.cache_data
def artwork(game_type='snakes'):
    if game_type == 'ludo':
        from ludo import board_svg as ludo_board
        return ludo_board()
    return board_svg([]).replace('width="640" height="740" viewBox="-20 -105 640 740"',
                                 'width="600" height="600" viewBox="0 0 600 600"')


def dispatch(action):
    state = st.session_state
    kind = action.get('action')
    if kind == 'home':
        state.local_game = None
        state.room = None
    elif kind == 'new':
        mode = action.get('mode', 'local')
        if mode not in ('local', 'computer'):
            raise GameError('Choose local or computer play.')
        count = int(action.get('count', 2))
        if mode == 'computer' and count < 2:
            raise GameError('Choose at least one computer opponent.')
        state.local_game = new_game(count, mode, game_type=action.get('game_type', 'snakes'), difficulty=action.get('difficulty', 'medium'))
        state.room = None
    elif kind == 'create':
        code = rooms().create(state.client, action.get('name'), int(action.get('count', 2)), action.get('game_type', 'snakes'), action.get('difficulty', 'medium'))
        state.room, state.local_game = code, None
    elif kind == 'join':
        code = str(action.get('code', '')).strip().upper()
        rooms().join(code, state.client, action.get('name'))
        state.room, state.local_game = code, None
    elif state.room and kind in ('start', 'roll', 'move', 'restart', 'arcade_move', 'snake_input', 'snake_start', 'tick', 'claim_draw'):
        rooms().action(state.room, state.client, kind, action.get('version'), action.get('token'), action.get('value'))
    elif state.local_game and kind in ('arcade_move', 'snake_input', 'snake_start', 'tick', 'claim_draw'):
        from arcade import move, snake_input, snake_start, chess_board, finish
        game = state.local_game
        if game['game_type'] not in TYPES: raise GameError('Choose an arcade game first.')
        if kind == 'arcade_move':
            computer = game['players'][game['turn']]['kind'] == 'computer'
            if computer != bool(action.get('computer')): raise GameError('Wait for the active player.')
            move(game, action.get('version'), action.get('value'), computer=computer)
        elif kind == 'claim_draw':
            if game['players'][game['turn']]['kind'] == 'computer' or game['game_type'] != 'chess' or game['finished'] or action.get('version') != game['version'] or not chess_board(game).can_claim_draw(): raise GameError('No draw can be claimed.')
            finish(game, [], 'Draw claimed by repetition or the fifty-move rule.'); game['version'] += 1
        else:
            if game['game_type'] != 'snake': raise GameError('Choose Snake Arena.')
            if kind == 'snake_start': snake_start(game)
            elif kind == 'tick': snake_tick(game)
            else:
                seat = int(action.get('seat', 0))
                if seat < 0 or seat >= len(game['players']) or game['players'][seat]['kind'] == 'computer': raise GameError('Choose your own snake.')
                snake_input(game, seat, action.get('value'))
    elif state.local_game and kind in ('roll', 'move'):
        game = state.local_game
        computer = game['players'][game['turn']]['kind'] == 'computer'
        if computer != bool(action.get('computer')):
            raise GameError('Wait for the active player.')
        if kind == 'move':
            if game.get('game_type') != 'ludo':
                raise GameError('Token selection is only used in Ludo.')
            from ludo import move_ludo
            move_ludo(game, action.get('version'), action.get('token'))
        else:
            play_turn(game, action.get('version'))
    elif state.local_game and kind == 'restart':
        game = state.local_game
        state.local_game = new_game(len(game['players']), game['mode'], game_type=game.get('game_type', 'snakes'), difficulty=game.get('difficulty', 'medium'))
    else:
        raise GameError('Choose a game to start playing.')


def payload():
    state = st.session_state
    game, seat, capacity = state.local_game, None, None
    if state.room:
        game, seat, capacity = rooms().snapshot(state.room, state.client)
    if game and game['game_type'] == 'snake' and not state.room: snake_tick(game)
    if game:
        game = {k:v for k,v in game.items() if not k.startswith('_')}
    from ludo import layout
    return {'invite': str(st.query_params.get('room', ''))[:6].upper(),
            'invite_game': st.query_params.get('game') if st.query_params.get('game') in ('snakes', 'ludo') + TYPES else 'snakes',
            'boards': {'snakes': artwork(), 'ludo': artwork('ludo')}, 'ludo_layout': layout(),
            'game': game, 'seat': seat, 'room': state.room, 'capacity': capacity,
            'error': state.error, 'ack': state.last_nonce, 'board': artwork(), 'now': time.time()}


def main():
    st.set_page_config(page_title='AIINC Arcade · Play Together', page_icon=str(ROOT / 'static' / 'controller.svg'), layout='wide', initial_sidebar_state='collapsed')
    st.markdown('''<style>
      [data-testid="stHeader"], footer {display:none}
      .stMainBlockContainer {padding:0!important;max-width:none!important}
      .stApp {background:#0b0b0b}
      [data-testid="stCustomComponentV1"] {width:100%}
    </style>''', unsafe_allow_html=True)
    for key, value in {'client': secrets.token_urlsafe(24), 'local_game': None, 'room': None, 'error': '', 'last_nonce': None}.items():
        if key not in st.session_state:
            st.session_state[key] = value

    @st.fragment(run_every='1s')
    def render():
        try:
            data = payload()
        except GameError as error:
            st.session_state.room = None
            st.session_state.error = str(error)
            data = payload()
        event = ui(data=data, key='clubhouse', default=None)
        if isinstance(event, dict) and event.get('nonce') and event['nonce'] != st.session_state.last_nonce:
            st.session_state.last_nonce = event['nonce']
            st.session_state.error = ''
            try:
                dispatch(event)
            except (GameError, ValueError, TypeError) as error:
                st.session_state.error = str(error)
            st.rerun(scope='fragment')
    render()


if __name__ == '__main__':
    main()
