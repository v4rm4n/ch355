# - ch355/api/game/engine.py -

import io
import chess
import chess.pgn

def process_move(pgn_string: str, uci_move: str) -> tuple[bool, str, str]:
    """
    Takes the current game history (PGN) and an incoming move (e.g., 'e2e4').
    Returns: (is_legal, new_pgn_string, match_status)
    """
    # 1. Load the current game state
    if not pgn_string:
        game = chess.pgn.Game()
    else:
        pgn_io = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            game = chess.pgn.Game()

    # Get the board state at the very end of the move history
    board = game.end().board()

    # 2. Parse the incoming move
    try:
        move = chess.Move.from_uci(uci_move)
    except chess.InvalidMoveError:
        return False, pgn_string, "invalid_format"

    # 3. Validate the move
    if move not in board.legal_moves:
        return False, pgn_string, "illegal_move"

    # 4. Apply the move
    game.end().add_variation(move)
    board.push(move)

    # 5. Determine the new game status
    status = "active"
    if board.is_checkmate():
        status = "completed"
    elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        status = "drawn" # You might need to add this to your MatchStatus Enum later!

    # 6. Export the updated move list
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
    new_pgn = str(game.accept(exporter))

    return True, new_pgn, status

def get_turn_color(pgn_string: str) -> str:
    """Returns 'white' or 'black' depending on whose turn it is."""
    if not pgn_string:
        return "white"
    
    pgn_io = io.StringIO(pgn_string)
    game = chess.pgn.read_game(pgn_io)
    
    if game is None:
        return "white"
        
    board = game.end().board()
    
    return "white" if board.turn == chess.WHITE else "black"