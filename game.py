"""Authoritative rules and thread-safe friend rooms. No browser-selected dice rolls."""
from copy import deepcopy
import random
import secrets
import threading
import time
import uuid

LADDERS = {2: 38, 7: 14, 8: 31, 15: 26, 21: 42, 28: 84, 36: 44, 51: 67, 71: 91, 78: 98}
SNAKES = {16: 6, 46: 25, 49: 11, 62: 19, 64: 60, 74: 53, 89: 68, 92: 88, 95: 75, 99: 80}


class GameError(ValueError):
    pass


def new_game(count=2, mode='local', name='You', game_type='snakes', difficulty='medium'):
    if not isinstance(count, int) or not 1 <= count <= 4:
        raise GameError('Choose between one and four players.')
    if mode not in ('local', 'computer', 'friends'):
        raise GameError('Choose a game mode.')
    from arcade import TYPES, validate_count
    if game_type not in ('snakes', 'ludo') + TYPES:
        raise GameError('Choose a game from the arcade.')
    if game_type in TYPES:
        validate_count(game_type, count, lobby=mode == 'friends')
    game = {
        'game_type': game_type, 'id': uuid.uuid4().hex, 'mode': mode, 'turn': 0, 'winner': None,
        'players': [{'name': (name if i == 0 else f'Computer {i}') if mode == 'computer' else f'Player {i+1}',
                     'kind': 'computer' if mode == 'computer' and i > 0 else 'human',
                     'position': 0} for i in range(count)],
        'dice': [None]*count, 'events': [], 'version': 0, 'ready_at': 0,
        'message': 'The adventure starts here. Roll the dice!', 'status': 'playing',
    }

    if game_type in TYPES:
        from arcade import initialise as init_arcade
        init_arcade(game, difficulty)
    if game_type == 'ludo':
        from ludo import initialise
        initialise(game)
    return game


def play_turn(game, expected_version, roll=None, now=None):
    """One atomic move, including the exact walking path used by the animation."""
    if game.get('game_type') == 'ludo':
        from ludo import roll_ludo
        return roll_ludo(game, expected_version, roll, now)
    if game.get('game_type') not in ('snakes', 'ludo'):
        raise GameError('Use this game’s move controls.')
    now = time.time() if now is None else now
    if game['status'] != 'playing' or game['winner'] is not None:
        raise GameError('This game is not taking turns right now.')
    if expected_version != game['version']:
        raise GameError('The board changed. Try your turn again.')
    if now < game['ready_at']:
        raise GameError('Let the current move finish first.')
    roll = random.randint(1, 6) if roll is None else roll
    if not isinstance(roll, int) or not 1 <= roll <= 6:
        raise GameError('Invalid dice roll.')
    player = game['turn']
    origin = game['players'][player]['position']
    landing = origin + roll
    walk = list(range(origin+1, landing+1)) if landing <= 100 else []
    destination = landing if walk else origin
    special = None
    if walk and landing in LADDERS:
        destination, special = LADDERS[landing], 'ladder'
    elif walk and landing in SNAKES:
        destination, special = SNAKES[landing], 'snake'
    game['players'][player]['position'] = destination
    game['dice'][player] = roll
    game['version'] += 1
    event = {'id': game['version'], 'player': player, 'roll': roll, 'origin': origin,
             'walk': walk, 'landing': landing if walk else origin,
             'destination': destination, 'special': special}
    game['events'] = (game['events'] + [event])[-20:]
    name = game['players'][player]['name']
    if not walk:
        message = f'{name} rolled {roll}. An exact roll is needed to reach 100.'
    elif special == 'ladder':
        message = f'{name} climbs a ladder! {landing} → {destination}'
    elif special == 'snake':
        message = f'A slippery surprise! {name}: {landing} → {destination}'
    else:
        message = f'{name} rolled {roll} and reached square {destination}.'
    if destination == 100:
        game['winner'] = player
        message = f'{name} reached 100. What a finish!'
    else:
        game['turn'] = (player+1) % len(game['players'])
    game['message'] = message
    fast = game['players'][player]['kind'] == 'computer'
    game['ready_at'] = now + (.45 + len(walk)*.07 + (.45 if special else 0) + .08 if fast else .85 + len(walk)*.17 + (1.05 if special else 0) + .35)
    return event


class RoomStore:
    """Rooms live for six hours in this single-replica server process."""
    def __init__(self):
        self.rooms = {}
        self.lock = threading.RLock()

    def _room(self, code):
        room = self.rooms.get(code)
        if not room or time.time()-room['updated'] > 21600:
            self.rooms.pop(code, None)
            raise GameError('Room not found or expired. Create a new room.')
        room['updated'] = time.time()
        return room

    def create(self, client, name, capacity, game_type='snakes', difficulty='medium'):
        if capacity not in (2, 3, 4):
            raise GameError('Friend rooms need two to four players.')
        from arcade import TYPES, validate_count
        if game_type in TYPES: validate_count(game_type, capacity)
        with self.lock:
            self.rooms = {k: v for k, v in self.rooms.items() if time.time()-v['updated'] < 21600}
            if len(self.rooms) >= 1000:
                raise GameError('All rooms are busy. Please try again later.')
            code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            while code in self.rooms:
                code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            game = new_game(1, 'friends', game_type=game_type, difficulty=difficulty)
            game['status'] = 'lobby'
            game['players'][0]['name'] = clean_name(name)
            self.rooms[code] = {'game': game, 'members': [client], 'capacity': capacity, 'updated': time.time()}
            return code

    def join(self, code, client, name):
        with self.lock:
            room = self._room(code)
            if client in room['members']:
                return
            if room['game']['status'] != 'lobby' or len(room['members']) >= room['capacity']:
                raise GameError('This room is full or the game has already started.')
            room['members'].append(client)
            player = {'name': clean_name(name), 'kind': 'human', 'position': 0}
            if room['game'].get('game_type') == 'ludo':
                player['tokens'] = [-1]*4
            room['game']['players'].append(player)
            room['game']['dice'].append(None)
            from arcade import TYPES, add_player
            if room['game']['game_type'] in TYPES: add_player(room['game'])

    def snapshot(self, code, client):
        with self.lock:
            room = self._room(code)
            if client not in room['members']:
                raise GameError('Join this room first.')
            if room['game']['game_type'] == 'snake':
                from arcade import snake_tick
                snake_tick(room['game'])
            return deepcopy(room['game']), room['members'].index(client), room['capacity']

    def action(self, code, client, action, version=None, token=None, value=None):
        with self.lock:
            room = self._room(code)
            if client not in room['members']:
                raise GameError('Join this room first.')
            seat = room['members'].index(client)
            game = room['game']
            if action in ('arcade_move', 'snake_input', 'snake_start', 'tick', 'claim_draw'):
                from arcade import TYPES, move, snake_input, snake_start, snake_tick, chess_board, finish
                if game['game_type'] not in TYPES: raise GameError('Choose an arcade game first.')
                if action in ('arcade_move', 'claim_draw'):
                    if seat != game['turn']: raise GameError('It is another player’s turn.')
                    if action == 'arcade_move': move(game, version, value)
                    else:
                        if game['game_type'] != 'chess' or game['status'] != 'playing' or game['finished'] or version != game['version'] or not chess_board(game).can_claim_draw(): raise GameError('No draw can be claimed.')
                        finish(game, [], 'Draw claimed by repetition or the fifty-move rule.'); game['version'] += 1
                else:
                    if game['game_type'] != 'snake': raise GameError('Choose Snake Arena.')
                    if action == 'snake_input': snake_input(game, seat, value)
                    elif action == 'snake_start':
                        if seat != 0: raise GameError('Only the host can start the arena.')
                        snake_start(game)
                    else: snake_tick(game)
            elif action == 'start':
                if seat != 0:
                    raise GameError('Only the room host can start the game.')
                if len(room['members']) != room['capacity']:
                    raise GameError('Wait for all players to join.')
                game['status'] = 'playing'
            elif action in ('roll', 'move'):
                if seat != game['turn']:
                    raise GameError('It is another player’s turn.')
                if action == 'move':
                    if game.get('game_type') != 'ludo':
                        raise GameError('Token selection is only used in Ludo.')
                    from ludo import move_ludo
                    move_ludo(game, version, token)
                else:
                    play_turn(game, version)
            elif action == 'restart':
                if seat != 0:
                    raise GameError('Only the room host can start a rematch.')
                if game['winner'] is None and not game.get('finished'):
                    raise GameError('Finish this game before starting a rematch.')
                fresh = new_game(len(game['players']), 'friends', game_type=game.get('game_type', 'snakes'), difficulty=game.get('difficulty', 'medium'))
                for i, p in enumerate(game['players']):
                    fresh['players'][i]['name'] = p['name']
                room['game'] = fresh
            else:
                raise GameError('Unknown room action.')


def clean_name(name):
    return str(name or 'Player').strip()[:24] or 'Player'
