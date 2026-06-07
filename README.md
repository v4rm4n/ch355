# CH355 Chess Backend Engine — Release Notes v1.0.0

## Executive Summary

Version `1.0.0` marks the completion of the core authoritative game state, synchronization, and timing engine for **CH355**. This release establishes a highly scalable, stateless backend built on **FastAPI**, **PostgreSQL**, and **Redis Pub/Sub**. The system is designed to act as a single source of truth for all chess interactions, protecting game integrity against client-side tampering while providing real-time synchronization to downstream clients.

## Core Features & Capabilities

1. **Authoritative Move Validation**

    - **Rule Enforcement:** Powered by backend python-chess validation. The server handles the entire game tree. Rogue, malformed, or out-of-turn Universal Chess Interface (UCI) strings are rejected before hitting the database.

    - **Turn Isolation:** Tracks active player turns continuously, rejecting valid moves if submitted by the wrong participant socket.

2. **Stateless Real-Time Clock Engine**

    - **Microsecond Precision Architecture:** Implements a reactive, timestamp-based delta clock system. Time is deducted based on the absolute interval between the current server call and the last_move_at database checkpoint.

    - **Dynamic Increments:** Fully parses standard chess time constraints (e.g., 10+5, 3+2) and automatically awards time increments upon successful legal moves.

    - **Untimed & Correspondence Support:** Detects "untimed" layouts to completely bypass clock deductions, formatting tags, and timestamp evaluations.

3. **Integrated Move-by-Move PGN Logging**

    - **Immutable Move Timelines:** Embeds standard clock metadata annotations ({[%clk hh:mm:ss.vvv]}) directly inside the main line of the Portable Game Notation (PGN) tree.

    - **Native Serialization:** Uses a unified exporter layout that natively strings together move histories along with comment structures, ensuring compatibility with standard external visualizers and analysis engines.

4. **Competitive Settlement & Rating Engine**

    - **Standard Elo Implementation:** Features an integrated Elo calculating engine using standard expected-score algorithms and adjustable $K$-factors.

    - **Atomic Profile Mutations:** Directly handles column updates for matches_played, matches_won, matches_lost, and matches_drawn fields inside postgres rows upon official game completion.

5. **Watertight Resolution Matrix**

    - **Elo-Safe Move-0 Abortion:** Gracefully cancels games that are exited prior to any moves being made (`pgn_moves == ""`), skipping profile penalties and reverting the match to a CANCELED status.

    - **Standard Resignations:** Computes and pays out Elo distributions immediately if a participant resigns from Move 1 onwards.

    - **Lazy-Evaluated Flag-Fall Protection:** Auto-terminates matches and crowns a winner via a timeout event if a player attempts a turn after their elapsed timeline balance drops below zero.

## API & Network Contract Specs

### REST Endpoints

**POST /match/create:** Spawns a game lobby with distinct options for private visibility, ranked flags, and explicit time formatting constraints.

**GET /match/open:** Surfaces public lobbies waiting for candidates, shielding players from their own generated rooms.

**POST /match/{id}/join:** Locks down an empty competitor seat, constructs starting clock values, and advances status to STARTING.

**POST /match/{id}/resign:** Processes move-0 aborts or standard forfeits mid-game.

**POST /match/{id}/draw:** Allows mutual agreements to split match ratings down the middle.

### WebSocket Gateways

**/game/ws/{match_id}:** High-throughput socket stream driving game execution. Handles incoming payload events and securely broadcasts state variables (`pgn`, `match_status`, `white_time_left`, `black_time_left`) to connected clients.


## System Hardening & Anti-Exploit Measures

**The "One Match Only" Firewall:** Prevents a single player account from simultaneously maintaining multiple `PENDING`, `STARTING`, or `ACTIVE` matches, shutting down concurrent lobby spamming and Elo farming exploits.

**Strict Payload Type Guards:** Validates type metrics on all incoming WebSocket fields using Pydantic schemas and string runtime checks, neutralizing raw data injections.

**Pylance Strict Conformance:** Refactored runtime variables and variables of union types to clear all strict control-flow unbound warnings.