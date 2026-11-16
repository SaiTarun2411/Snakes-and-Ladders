"""Server-authoritative arcade rules, chess opponents and shared Snake arenas."""
from functools import lru_cache
import random
import time
import chess
from game import GameError

TYPES = ('tictactoe', 'dots', 'connect4', 'chess', 'snake', 'math')
TITLES = {'tictactoe': 'Tic Tac Toe', 'dots': 'Dots & Boxes', 'connect4': 'Four in a Row',
          'chess': 'Chess', 'snake': 'Snake Arena', 'math': 'Math Rush'}


def validate_count(kind, count, lobby=False):
    if lobby and count == 1:
        return
    allowed = (2,) if kind in ('tictactoe', 'connect4', 'chess') else (1, 2) if kind == 'snake' else (1, 2, 3, 4) if kind == 'math' else (2, 3, 4)
    if count not in allowed:
        raise GameError('Choose a supported player count for this game.')


def initialise(g, difficulty='medium'):
    if difficulty not in ('easy', 'medium', 'hard'):
        raise GameError('Choose Easy, Medium or Hard.')
    g.update(difficulty=difficulty, finished=False, scores=[0]*len(g['players']))
    kind = g['game_type']
    if kind == 'tictactoe':
        g['cells'] = [None]*9
    elif kind == 'connect4':
        g['cells'] = [None]*42
    elif kind == 'dots':
        g.update(edges={}, boxes=[None]*16)
    elif kind == 'chess':
        g.update(moves=[], fen=chess.STARTING_FEN, legal=[m.uci() for m in chess.Board().legal_moves], last_move=None)
    elif kind == 'snake':
        g.update(snakes=[], food=[], ticks=0, started=False, last_tick=0)
        prepare_snake(g)
    elif kind == 'math':
        g.update(questions_done=0, math_feedback='')
        next_question(g)
    g['message'] = 'Choose a square to begin.' if kind == 'tictactoe' else 'Ready to play. Your move!'
    return g


def add_player(g):
    g['scores'].append(0)
    if g['game_type'] == 'snake':
        prepare_snake(g)


def finish(g, winners, message):
    g['finished'] = True
    g['winner'] = winners[0] if len(winners) == 1 else None
    g['message'] = message


def finish_scores(g):
    top = max(g['scores'])
    winners = [i for i, score in enumerate(g['scores']) if score == top]
    names = ', '.join(g['players'][i]['name'] for i in winners)
    finish(g, winners, f'{names} {"wins" if len(winners) == 1 else "tie"} with {top} points!')


def lines(cells, width, height, length):
    for r in range(height):
        for c in range(width):
            p = cells[r*width+c]
            if p is None:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_r, end_c = r+(length-1)*dr, c+(length-1)*dc
                if 0 <= end_r < height and 0 <= end_c < width:
                    indexes = [(r+i*dr)*width+c+i*dc for i in range(length)]
                    if all(cells[i] == p for i in indexes):
                        return p, indexes
    return None, []


def box_edges(r, c):
    return [f'h-{r}-{c}', f'h-{r+1}-{c}', f'v-{r}-{c}', f'v-{r}-{c+1}']


def legal_edges(g):
    return [f'{axis}-{r}-{c}' for axis, rows, cols in (('h', 5, 4), ('v', 4, 5))
            for r in range(rows) for c in range(cols) if f'{axis}-{r}-{c}' not in g['edges']]


def chess_board(g):
    b = chess.Board()
    for uci in g['moves']:
        b.push_uci(uci)
    return b


def next_question(g):
    a, b = random.randint(2, 12), random.randint(2, 12)
    op = random.choice(('+', '−', '×', '÷'))
    if op == '+': answer = a+b
    elif op == '−': a, b = max(a, b), min(a, b); answer = a-b
    elif op == '×': answer = a*b
    else: a, answer = a*b, a
    options = {answer}
    while len(options) < 4:
        options.add(max(0, answer+random.randint(-12, 12)))
    choices = list(options); random.shuffle(choices)
    g['question'] = {'text': f'{a} {op} {b}', 'options': choices}
    g['_answer'] = answer


def validate(g, version):
    if g['status'] != 'playing' or g.get('finished'):
        raise GameError('This game is not taking moves right now.')
    if version != g['version']:
        raise GameError('The board changed. Try again.')


def move(g, version, value=None, computer=False, now=None):
    validate(g, version)
    kind, seat = g['game_type'], g['turn']
    if kind == 'snake':
        raise GameError('Use the Snake direction controls.')
    if computer:
        value = computer_move(g)
    if kind in ('tictactoe', 'connect4'):
        limit = 9 if kind == 'tictactoe' else 7
        if type(value) is not int or not 0 <= value < limit:
            raise GameError('Choose an empty square or column.')
        index = value
        if kind == 'connect4':
            index = next((r*7+value for r in range(5, -1, -1) if g['cells'][r*7+value] is None), None)
        if index is None or g['cells'][index] is not None:
            raise GameError('That square or column is full.')
        g['cells'][index] = seat
        if kind == 'connect4':
            g['last_drop'] = {'id':g['version']+1, 'index':index, 'player':seat}
        winner, winning = lines(g['cells'], 3 if kind == 'tictactoe' else 7, 3 if kind == 'tictactoe' else 6, 3 if kind == 'tictactoe' else 4)
        g['winning'] = winning
        if winner is not None:
            finish(g, [winner], f'{g["players"][winner]["name"]} wins!')
        elif None not in g['cells']:
            finish(g, [], 'A draw! Play again?')
        g['turn'] = 1-seat
    elif kind == 'dots':
        if not isinstance(value, str) or value not in legal_edges(g):
            raise GameError('Choose an unclaimed edge.')
        g['edges'][value] = seat
        captured = 0
        for r in range(4):
            for c in range(4):
                if g['boxes'][r*4+c] is None and all(e in g['edges'] for e in box_edges(r, c)):
                    g['boxes'][r*4+c] = seat; g['scores'][seat] += 1; captured += 1
        if not captured:
            g['turn'] = (seat+1) % len(g['players'])
        if None not in g['boxes']:
            finish_scores(g)
    elif kind == 'chess':
        b = chess_board(g)
        try:
            m = chess.Move.from_uci(value) if isinstance(value, str) else None
        except ValueError:
            m = None
        if m not in b.legal_moves:
            raise GameError('Choose a legal chess move.')
        san = b.san(m); b.push(m)
        g['moves'].append(value)
        g.update(fen=b.fen(), legal=[m.uci() for m in b.legal_moves], last_move=value, last_san=san)
        g['turn'] = 0 if b.turn == chess.WHITE else 1
        outcome = b.outcome()
        if outcome:
            winner = None if outcome.winner is None else (0 if outcome.winner else 1)
            reason = outcome.termination.name.replace('_', ' ').lower()
            finish(g, [] if winner is None else [winner], f'Draw: {reason}.' if winner is None else f'{g["players"][winner]["name"]} wins by {reason}!')
        else:
            g['message'] = san + (' · Check!' if b.is_check() else '')
        g['can_claim_draw'] = b.can_claim_draw() if not g['finished'] else False
    elif kind == 'math':
        if type(value) is not int or value not in g['question']['options']:
            raise GameError('Choose one of the answer buttons.')
        correct = value == g['_answer']
        g['scores'][seat] += 10 if correct else 0
        g['math_feedback'] = f'{g["players"][seat]["name"]}: {g["question"]["text"]} = {g["_answer"]}. ' + ('+10 points!' if correct else 'Keep going!')
        g['questions_done'] += 1
        if g['questions_done'] >= 10*len(g['players']):
            finish_scores(g)
        else:
            g['turn'] = (seat+1) % len(g['players']); next_question(g)
    g['version'] += 1
    if not g['finished'] and kind != 'chess':
        g['message'] = f'{g["players"][g["turn"]]["name"]} to play.'
    return g


VALUES = {chess.PAWN:100, chess.KNIGHT:320, chess.BISHOP:330, chess.ROOK:500, chess.QUEEN:900, chess.KING:0}


def evaluate(b):
    if b.is_checkmate(): return -100000
    if b.is_stalemate() or b.is_insufficient_material(): return 0
    score = 0
    for square, piece in b.piece_map().items():
        rank, file = chess.square_rank(square), chess.square_file(square)
        center = 3.5-abs(file-3.5) + 3.5-abs(rank-3.5)
        bonus = center*6 if piece.piece_type in (chess.KNIGHT, chess.BISHOP) else 0
        if piece.piece_type == chess.PAWN:
            bonus = (rank if piece.color else 7-rank)*7
        score += (VALUES[piece.piece_type]+bonus) * (1 if piece.color == b.turn else -1)
    return score


def choose_chess(g):
    b = chess_board(g); moves = list(b.legal_moves)
    if g['difficulty'] == 'easy': return random.choice(moves).uci()
    deadline = time.monotonic() + (.35 if g['difficulty'] == 'hard' else .12)
    def ordered(board):
        return sorted(board.legal_moves, key=lambda m: (bool(m.promotion), board.is_capture(m), board.gives_check(m)), reverse=True)
    def search(depth, alpha, beta):
        if time.monotonic() > deadline: raise TimeoutError
        if not depth or b.is_game_over(): return evaluate(b)
        best = -1000000
        for m in ordered(b):
            b.push(m)
            try: score = -search(depth-1, -beta, -alpha)
            finally: b.pop()
            best = max(best, score); alpha = max(alpha, score)
            if alpha >= beta: break
        return best
    best = moves[0]
    for depth in range(1, (3 if g['difficulty'] == 'medium' else 4)+1):
        candidate, score_best = best, -1000000
        try:
            for m in ordered(b):
                b.push(m)
                try: score = -search(depth-1, -1000000, -score_best)
                finally: b.pop()
                if score > score_best: candidate, score_best = m, score
        except TimeoutError:
            break
        best = candidate
    return best.uci()


@lru_cache(maxsize=20000)
def ttt_score(cells, player, computer):
    """Reuse equivalent positions instead of re-searching every move ordering."""
    winner, _ = lines(cells, 3, 3, 3)
    if winner is not None: return 1 if winner == computer else -1
    free = [i for i, cell in enumerate(cells) if cell is None]
    if not free: return 0
    scores = [ttt_score(cells[:i]+(player,)+cells[i+1:], 1-player, computer) for i in free]
    return (max if player == computer else min)(scores)


def computer_move(g):
    kind, seat = g['game_type'], g['turn']
    if kind == 'chess': return choose_chess(g)
    if kind == 'math':
        options = g['question']['options']
        return g['_answer'] if random.random() < .8 else random.choice([x for x in options if x != g['_answer']])
    if kind == 'dots':
        edges = legal_edges(g)
        for e in edges:
            if any(g['boxes'][r*4+c] is None and e in box_edges(r,c) and sum(x in g['edges'] for x in box_edges(r,c)) == 3 for r in range(4) for c in range(4)):
                return e
        safe = [e for e in edges if not any(e in box_edges(r,c) and sum(x in g['edges'] for x in box_edges(r,c)) == 2 for r in range(4) for c in range(4))]
        return random.choice(safe or edges)
    width, height, length = (3,3,3) if kind == 'tictactoe' else (7,6,4)
    choices = [i for i in range(width*height) if g['cells'][i] is None] if kind == 'tictactoe' else [i for i in range(7) if g['cells'][i] is None]
    for p in (seat, 1-seat):
        for value in choices:
            cells = g['cells'][:]
            index = value if kind == 'tictactoe' else next(r*7+value for r in range(5,-1,-1) if cells[r*7+value] is None)
            cells[index] = p
            if lines(cells,width,height,length)[0] == p: return value
    if kind == 'tictactoe':
        return max(choices,key=lambda i: ttt_score(tuple(g['cells'][:i]+[seat]+g['cells'][i+1:]),1-seat,seat))
    return min(choices,key=lambda i:abs(i-3))


DIRECTIONS = {'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}


def prepare_snake(g):
    g['snakes'] = [{'body': [[4,5],[3,5],[2,5]], 'direction':'right', 'next':'right', 'alive':True},
                   {'body': [[15,14],[16,14],[17,14]], 'direction':'left', 'next':'left', 'alive':True}][:len(g['players'])]
    g['food'] = []; food(g)


def food(g):
    occupied = {tuple(p) for s in g['snakes'] for p in s['body']} | {tuple(p) for p in g['food']}
    free = [(x,y) for x in range(20) for y in range(20) if (x,y) not in occupied]
    while len(g['food']) < 3 and free:
        pos = random.choice(free);free.remove(pos);g['food'].append(list(pos))


def snake_input(g, seat, value, now=None):
    if g['status'] != 'playing' or g['finished']:
        raise GameError('Start a new arena to play.')
    if not isinstance(value, str) or value not in DIRECTIONS:
        raise GameError('Choose a direction.')
    s = g['snakes'][seat]
    if not s['alive']: raise GameError('Your snake is out. Wait for the result.')
    dx,dy = DIRECTIONS[s['direction']]; nx,ny = DIRECTIONS[value]
    if (dx+nx,dy+ny) != (0,0): s['next'] = value
    g['version'] += 1


def snake_start(g, now=None):
    if g['status'] != 'playing' or g['finished'] or g['started']:
        raise GameError('The arena has already started or finished.')
    g['started'] = True; g['last_tick'] = time.time() if now is None else now
    g['message'] = 'Collect stars. Avoid walls and snakes!'
    g['version'] += 1


def snake_tick(g, now=None):
    now = time.time() if now is None else now
    if g['status'] != 'playing' or g['finished'] or not g['started']:
        return
    # At most one step per request; no hidden fast-forward when a tab returns.
    if now-g['last_tick'] < .22: return
    g['last_tick'] = now
    occupied = {tuple(p) for s in g['snakes'] if s['alive'] for p in s['body']}
    for i,s in enumerate(g['snakes']):
        if s['alive'] and g['players'][i]['kind'] == 'computer':
            candidates=[]
            dx,dy=DIRECTIONS[s['direction']]
            for direction,(x,y) in DIRECTIONS.items():
                head=(s['body'][0][0]+x,s['body'][0][1]+y)
                if (x+dx,y+dy)!=(0,0) and all(0<=v<20 for v in head) and head not in occupied:
                    distance=min(abs(head[0]-f[0])+abs(head[1]-f[1]) for f in g['food']) if g['food'] else 0
                    candidates.append((distance,direction))
            if candidates:s['next']=min(candidates)[1]
    heads={}
    for i,s in enumerate(g['snakes']):
        if s['alive']:
            s['direction']=s['next'];dx,dy=DIRECTIONS[s['direction']]
            heads[i]=[s['body'][0][0]+dx,s['body'][0][1]+dy]
    # Tails vacate unless eating, so moving into a vacating tail is legal.
    bodies={tuple(p) for i,s in enumerate(g['snakes']) if s['alive'] for p in (s['body'] if heads[i] in g['food'] else s['body'][:-1])}
    for i,head in heads.items():
        s=g['snakes'][i]
        swap=any(j!=i and head==g['snakes'][j]['body'][0] and heads[j]==s['body'][0] for j in heads)
        if any(v<0 or v>=20 for v in head) or tuple(head) in bodies or sum(h==head for h in heads.values())>1 or swap:
            s['alive']=False
    for i,head in heads.items():
        s=g['snakes'][i]
        if s['alive']:
            s['body'].insert(0,head)
            if head in g['food']:g['food'].remove(head);g['scores'][i]+=10
            else:s['body'].pop()
    food(g);g['ticks']+=1;g['version']+=1
    alive=[i for i,s in enumerate(g['snakes']) if s['alive']]
    if len(g['snakes'])>1 and len(alive)<2:
        finish(g,alive,f'{g["players"][alive[0]]["name"]} wins the arena!' if alive else 'Both snakes are out. A draw!')
    elif len(g['snakes'])==1 and (not alive or g['scores'][0]>=120):
        finish(g,[0] if alive else [],f'Solo run complete: {g["scores"][0]} points!')
    elif g['ticks']>=600:finish_scores(g)
