import unittest
from concurrent.futures import ThreadPoolExecutor
import chess
from arcade import TYPES, move, computer_move, snake_start, snake_input, snake_tick, legal_edges, box_edges
from game import GameError, RoomStore, new_game, play_turn


class ArcadeRules(unittest.TestCase):
    def play(self, g, value):
        return move(g, g['version'], value)

    def test_tic_tac_toe_win_and_finished_guard(self):
        g=new_game(game_type='tictactoe')
        for v in [0,3,1,4,2]: self.play(g,v)
        self.assertEqual(g['winner'],0)
        self.assertEqual(g['winning'],[0,1,2])
        with self.assertRaises(GameError):self.play(g,8)

    def test_tic_tac_toe_draw(self):
        g=new_game(game_type='tictactoe')
        for v in [0,1,2,4,3,5,7,6,8]:self.play(g,v)
        self.assertTrue(g['finished']);self.assertIsNone(g['winner'])

    def test_replay_occupied_and_dice_rejected(self):
        g=new_game(game_type='tictactoe');self.play(g,0)
        for value in [0,-1,9,True,'1']:
            with self.assertRaises(GameError):self.play(g,value)
        with self.assertRaises(GameError):move(g,0,1)
        with self.assertRaises(GameError):play_turn(g,1)
        self.assertEqual(g['version'],1)

    def test_tic_tac_toe_computer_never_loses(self):
        def visit(g):
            if g['finished']:
                self.assertNotEqual(g['winner'],0);return
            if g['turn']==1:
                self.play(g,computer_move(g));visit(g)
            else:
                from copy import deepcopy
                for v,c in enumerate(g['cells']):
                    if c is None:
                        nxt=deepcopy(g);self.play(nxt,v);visit(nxt)
        visit(new_game(2,'computer',game_type='tictactoe'))

    def test_connect_four_vertical_horizontal_diagonal(self):
        for values in ([0,1,0,1,0,1,0],[0,6,1,6,2,6,3],[0,1,1,2,6,2,2,3,6,3,5,3,3]):
            g=new_game(game_type='connect4')
            for v in values:self.play(g,v)
            self.assertEqual(g['winner'],0)

    def test_connect_four_full_column(self):
        g=new_game(game_type='connect4')
        for _ in range(6):self.play(g,0)
        with self.assertRaises(GameError):self.play(g,0)

    def test_dots_capture_retains_turn_and_double_box(self):
        g=new_game(game_type='dots')
        shared='v-0-1'
        for e in set(box_edges(0,0)+box_edges(0,1))-{shared}:g['edges'][e]=1
        self.play(g,shared)
        self.assertEqual(g['scores'],[2,0]);self.assertEqual(g['turn'],0)
        with self.assertRaises(GameError):self.play(g,shared)
        self.play(g,'h-4-0');self.assertEqual(g['turn'],1)

    def test_dots_complete_all_boxes(self):
        g=new_game(4,game_type='dots')
        for e in legal_edges(g):self.play(g,e)
        self.assertTrue(g['finished']);self.assertEqual(sum(g['scores']),16)
        self.assertNotIn(None,g['boxes'])

    def test_chess_checkmate_and_illegal_moves(self):
        g=new_game(game_type='chess')
        with self.assertRaises(GameError):self.play(g,'e2e5')
        for m in ['f2f3','e7e5','g2g4','d8h4']:self.play(g,m)
        self.assertTrue(g['finished']);self.assertEqual(g['winner'],1)
        self.assertIn('checkmate',g['message'])

    def test_chess_castling_and_en_passant(self):
        g=new_game(game_type='chess')
        for m in ['e2e4','e7e5','g1f3','b8c6','f1c4','g8f6','e1g1']:self.play(g,m)
        self.assertEqual(chess.Board(g['fen']).piece_at(chess.F1).symbol(),'R')
        g=new_game(game_type='chess')
        for m in ['e2e4','a7a6','e4e5','d7d5','e5d6']:self.play(g,m)
        self.assertIsNone(chess.Board(g['fen']).piece_at(chess.D5))

    def test_chess_promotion_stalemate_and_repetition(self):
        g=new_game(game_type='chess')
        for m in ['a2a4','h7h5','a4a5','h5h4','a5a6','h4h3','a6b7','h3g2','b7a8n']:self.play(g,m)
        self.assertEqual(chess.Board(g['fen']).piece_at(chess.A8).symbol(),'N')
        g=new_game(game_type='chess')
        for _ in range(2):
            for m in ['g1f3','g8f6','f3g1','f6g8']:self.play(g,m)
        self.assertTrue(g['can_claim_draw'])

    def test_all_chess_difficulties_choose_legal_moves(self):
        for level in ['easy','medium','hard']:
            g=new_game(2,'computer',game_type='chess',difficulty=level)
            self.play(g,'e2e4')
            selected=computer_move(g)
            self.assertIn(selected,g['legal'])
            move(g,g['version'],computer=True)
            self.assertEqual(len(g['moves']),2)
        with self.assertRaises(GameError):new_game(game_type='chess',difficulty='impossible')

    def test_math_scoring_equal_questions_and_finish(self):
        g=new_game(3,game_type='math')
        totals=[0,0,0]
        for i in range(30):
            self.assertEqual(g['turn'],i%3)
            self.assertEqual(len(set(g['question']['options'])),4)
            self.assertIn(g['_answer'],g['question']['options'])
            totals[g['turn']]+=1;self.play(g,g['_answer'])
        self.assertEqual(totals,[10]*3);self.assertEqual(g['scores'],[100]*3)
        self.assertTrue(g['finished']);self.assertIsNone(g['winner'])

    def test_math_incorrect_answer_does_not_score(self):
        g=new_game(1,game_type='math')
        wrong=next(n for n in g['question']['options'] if n!=g['_answer'])
        self.play(g,wrong);self.assertEqual(g['scores'],[0]);self.assertEqual(g['questions_done'],1)

    def test_snake_growth_no_reversal_and_rate_limit(self):
        g=new_game(1,game_type='snake');g['food']=[[5,5],[10,10],[12,12]]
        snake_start(g,now=100);snake_input(g,0,'left')
        self.assertEqual(g['snakes'][0]['next'],'right')
        snake_tick(g,now=100.1);self.assertEqual(g['ticks'],0)
        snake_tick(g,now=100.3)
        self.assertEqual(g['scores'],[10]);self.assertEqual(len(g['snakes'][0]['body']),4)
        snake_input(g,0,'up');snake_tick(g,now=100.6)
        self.assertEqual(g['snakes'][0]['body'][0],[5,4])

    def test_snake_simultaneous_collision_is_draw(self):
        g=new_game(2,game_type='snake')
        g['snakes'][0]['body']=[[9,10],[8,10],[7,10]]
        g['snakes'][1]['body']=[[11,10],[12,10],[13,10]]
        snake_start(g,now=100);snake_tick(g,now=101)
        self.assertTrue(g['finished']);self.assertIsNone(g['winner'])
        self.assertFalse(any(s['alive'] for s in g['snakes']))

    def test_snake_last_survivor(self):
        g=new_game(2,game_type='snake');g['snakes'][0]['body']=[[19,5],[18,5],[17,5]]
        snake_start(g,now=100);snake_tick(g,now=101)
        self.assertEqual(g['winner'],1)

    def test_player_count_restrictions(self):
        for kind in ['tictactoe','connect4','chess']:
            for count in [1,3,4]:
                with self.assertRaises(GameError):new_game(count,game_type=kind)
        with self.assertRaises(GameError):new_game(4,game_type='snake')


class ArcadeRooms(unittest.TestCase):
    def room(self,kind):
        store=RoomStore();code=store.create('a','Alice',2,kind)
        store.join(code,'b','Bob');store.action(code,'a','start')
        return store,code

    def test_every_game_has_shared_room_and_only_owner_moves(self):
        first={'tictactoe':0,'dots':'h-0-0','connect4':3,'chess':'e2e4','math':None}
        for kind in TYPES:
            store,code=self.room(kind)
            g,_,_=store.snapshot(code,'a')
            self.assertEqual(len(g['players']),2)
            if kind=='snake':
                self.assertEqual(len(g['snakes']),2)
                with self.assertRaises(GameError):store.action(code,'b','snake_start')
                store.action(code,'a','snake_start')
                store.action(code,'b','snake_input',value='up')
            else:
                value=g['_answer'] if kind=='math' else first[kind]
                with self.assertRaises(GameError):store.action(code,'b','arcade_move',0,value=value)
                store.action(code,'a','arcade_move',0,value=value)
            a,_,_=store.snapshot(code,'a');b,_,_=store.snapshot(code,'b')
            self.assertEqual(a,b)
            with self.assertRaises(GameError):store.action(code,'intruder','tick')

    def test_atomic_duplicate_move(self):
        store,code=self.room('tictactoe')
        def attempt(_):
            try:store.action(code,'a','arcade_move',0,value=0);return True
            except GameError:return False
        with ThreadPoolExecutor(4) as pool:self.assertEqual(sum(pool.map(attempt,range(4))),1)

    def test_room_draw_rematch_and_host_only(self):
        store,code=self.room('tictactoe')
        for i,v in enumerate([0,1,2,4,3,5,7,6,8]):store.action(code,'a' if i%2==0 else 'b','arcade_move',i,value=v)
        with self.assertRaises(GameError):store.action(code,'b','restart')
        store.action(code,'a','restart')
        g,_,_=store.snapshot(code,'b')
        self.assertFalse(g['finished']);self.assertEqual(g['players'][1]['name'],'Bob')

    def test_wrong_room_capacity(self):
        with self.assertRaises(GameError):RoomStore().create('a','Alice',4,'chess')


if __name__=='__main__':unittest.main()
