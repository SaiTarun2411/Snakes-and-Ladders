# AIINC Arcade

Eight games share the matte-black and metallic-gold catalogue at https://game.aiinc.uk.

| Game | Local players | Computer mode | Private room |
| --- | --- | --- | --- |
| Snakes & Ladders | 1–4 | 1 human + 1–3 computers | 2–4 |
| Ludo | 1–4 | 1 human + 1–3 computers | 2–4 |
| Tic Tac Toe | 2 | 1 human + 1 computer | 2 |
| Dots & Boxes | 2–4 | 1 human + 1–3 computers | 2–4 |
| Four in a Row | 2 | 1 human + 1 computer | 2 |
| Chess | 2 | Easy / Medium / Hard | 2 |
| Snake Arena | 1–2 | 1 human + 1 computer | 2 |
| Math Rush | 1–4 | 1 human + 1–3 computers | 2–4 |

Chess uses the `chess` Python library for legal moves, castling, en passant, promotion, checkmate, stalemate, and automatic draw rules. Players can claim a draw when repetition or the fifty-move rule allows it. Easy chooses random legal moves. Medium and Hard use bounded iterative-deepening alpha-beta search with material and positional evaluation; Hard has a higher depth and time budget. These are casual opponents, not rated engines.

Dots & Boxes uses a 5×5 dot grid (16 boxes). Completing a box earns a point and another turn. A shared edge may capture two boxes. Four in a Row checks vertical, horizontal, and both diagonal lines. Tic Tac Toe uses an optimal computer opponent.

Snake Arena has a 20×20 shared board. Start the arena, collect stars, and avoid walls and bodies. Arrow keys or on-screen controls steer Player 1; WASD steers Player 2 in local two-player matches. Solo and computer modes accept either key set for the human. Online each player controls only their own snake. Stars earn 10 points. Last survivor wins; simultaneous elimination draws. Solo wins at 120 points. At 600 steps the highest score wins. Movement is server-authoritative and network-paced; keep the tab active. Touch arrows are available on mobile.

Math Rush gives each player ten questions using addition, subtraction, multiplication, and exact division. Correct answers earn ten points. Players take turns; highest score wins. Answers stay on the server until each answer is submitted.

Room codes and direct invitation links work for all eight games. Only the host starts a room or starts a rematch; players control their own seats. Rooms are held in one server process and expire after six hours of inactivity. Restarting or deploying the app ends active rooms.

## Validation

```sh
python3 -m unittest discover -s tests -v
streamlit run app.py --server.headless true
python3 scripts/check_arcade_protocol.py
```

The protocol check exercises the actual app with independent sessions for all six new games, covering creation, computer turns, friend-room joins, and shared moves. Set `GAME_TEST_URL=https://game.aiinc.uk` to run it against the live deployment.

## Current hosting

The custom domain is served by Azure Container App `snakes-and-ladders-web`, resource group `SaiTarunRG`, subscription `Azure for Students`. GitHub Actions publishes commit-tagged images to `ghcr.io/saitarun2411/snakes-and-ladders`. Deploy the successful image with `az containerapp update`, preserving the existing ingress, domain, single-replica limit, and registry configuration.
