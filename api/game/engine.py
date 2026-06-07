# - ch355/api/game/engine.py -

import io
import chess
import chess.pgn

def process_move(pgn_moves: str, uci_move: str, clock_annotation: str | None = None) -> tuple[bool, str, str]:
    """
    Validates and applies a move. 
    Attaches clock metadata directly to the move node so it is permanently preserved in the PGN history.
    """
    # 1. Initialize board from existing PGN history
    game = chess.pgn.read_game(io.StringIO(pgn_moves)) if pgn_moves else chess.pgn.Game()
    if not game:
        game = chess.pgn.Game()
        
    # 💡 FIXED: Use python-chess's native .end() method to hop straight to the last move node
    node = game.end()
    board = node.board()
    
    # 2. Parse and validate the new incoming move
    try:
        move = chess.Move.from_uci(uci_move)
    except ValueError:
        return False, pgn_moves, "active"
        
    if move not in board.legal_moves:
        return False, pgn_moves, "active"
        
    # 3. Apply the move to the game tree node
    new_node = node.add_main_variation(move)
    
    # 💡 ATTACH THE CLOCK COMMENT DIRECTLY TO THE NODE
    if clock_annotation:
        new_node.comment = clock_annotation
        
    # 4. Determine engine completion status
    next_board = new_node.board()
    if next_board.is_game_over():
        status = "completed"
    elif next_board.is_stalemate() or next_board.is_insufficient_material():
        status = "drawn"
    else:
        status = "active"
        
    # 5. Export clean PGN string containing all historical comments intact
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=True)
    new_pgn = game.accept(exporter)
    
    return True, new_pgn.strip(), status

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