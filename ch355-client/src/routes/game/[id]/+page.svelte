<!-- src/routes/game/[id]/+page.svelte -->
<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { Chessground } from 'svelte-chessground';
    import { Chess } from 'chess.js';
    import { get } from 'svelte/store';

    import {
        is_authenticated, current_user, active_match, my_color,
        ws_connected, access_token
    } from '$lib/stores';
    import { api, ws_url } from '$lib/api';
    import { format_clock, strip_pgn_comments } from '$lib/chess_utils';
    import type { Match } from '$lib/stores';

    const match_id = $page.params.id;

    let socket: WebSocket | null = null;
    let chess = new Chess();
    let dests = $state<Map<string, string[]>>(new Map());
    let move_history = $state<string[]>([]);
    let confirming_resign = $state(false);
    let confirming_draw = $state(false);
    let status_msg = $state('AWAITING OPPONENT...');
    let clock_interval: ReturnType<typeof setInterval> | null = null;
    let poll_interval: ReturnType<typeof setInterval> | null = null; // kept for cleanup safety
    let white_time_display = $state<number | null>(null);
    let black_time_display = $state<number | null>(null);
    // Timestamp (ms) of last server clock sync; used to tick locally
    let white_time_ts = 0;
    let black_time_ts = 0;
    let is_my_turn = $state(false);
    let both_connected = $state(false);
    // IDs of users we've seen connect via WS events (our own + opponent)
    let seen_connections = new Set<string>();
    // Names keyed by user ID, populated from PLAYER_CONNECTED events
    let player_names = $state<Record<string, string>>({});

    // Derived: opponent's name
    const opponent_id = $derived(
        $my_color === 'white' ? match_data?.black_player_id : match_data?.white_player_id
    );
    const opponent_name = $derived(
        (opponent_id && player_names[opponent_id]) ? player_names[opponent_id] : null
    );

    // Chessground config state
    let cg_fen = $state('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
    let cg_api: any = null;
    let cg_orientation = $state<'white' | 'black'>('white');
    let cg_last_move = $state<[string, string] | undefined>(undefined);
    let match_data = $state<Match | null>(null);
    let game_over = $state<{ reason: string; winner_id?: string; w_change?: number | null; b_change?: number | null } | null>(null);

    // Pending move waiting for server confirmation
    let pending_move: { from: string; to: string; promo?: string } | null = null;

    // ──────────────────────────────────────────────
    // Board logic
    // ──────────────────────────────────────────────

    function compute_dests(): Map<string, string[]> {
        const map = new Map<string, string[]>();
        const moves = chess.moves({ verbose: true });
        for (const move of moves) {
            if (!map.has(move.from)) map.set(move.from, []);
            map.get(move.from)!.push(move.to);
        }
        return map;
    }

function sync_board_from_chess() {
        cg_fen = chess.fen();

        const turn = chess.turn() === 'w' ? 'white' : 'black';
        is_my_turn = turn === $my_color && both_connected && 
                     (match_data?.status === 'active' || match_data?.status === 'starting');
        dests = is_my_turn ? compute_dests() : new Map();
        move_history = chess.history();

        if (chess.isGameOver()) {
            if (chess.isCheckmate()) status_msg = 'CHECKMATE';
            else if (chess.isDraw()) status_msg = 'DRAW';
            else status_msg = 'GAME OVER';
        } else if (chess.isCheck()) {
            status_msg = 'CHECK!';
        } else if (!both_connected) {
            status_msg = 'AWAITING OPPONENT...';
        } else {
            status_msg = is_my_turn ? 'YOUR TURN' : 'OPPONENT\'S TURN';
        }

        // --- THE FORCE UPDATE ---
        // If the board API is ready, aggressively push the new rules into it.
        if (cg_api) {
            cg_api.set({
                turnColor: turn,
                movable: {
                    color: is_waiting ? undefined : ($my_color ?? undefined),
                    dests: dests,
                    free: false
                }
            });
        }
    }

    function load_pgn_safe(pgn: string) {
        if (!pgn || pgn.trim() === '') {
            chess.reset();
            sync_board_from_chess();
            return;
        }
        // Try loading full PGN first (with comments)
        try {
            chess.loadPgn(pgn, { sloppy: true });
            sync_board_from_chess();
            return;
        } catch {}

        // Strip comments and retry
        try {
            chess.loadPgn(strip_pgn_comments(pgn), { sloppy: true });
            sync_board_from_chess();
            return;
        } catch {}

        // Last resort: replay move tokens
        chess.reset();
        const tokens = strip_pgn_comments(pgn).split(/\s+/);
        for (const tok of tokens) {
            if (!tok || tok.match(/^\d+\./)) continue;
            try { chess.move(tok); } catch { break; }
        }
        sync_board_from_chess();
    }

    // ──────────────────────────────────────────────
    // Clock
    // ──────────────────────────────────────────────

    function sync_clocks_from_server(wt: number | null, bt: number | null) {
        const now = Date.now();
        if (wt !== null && wt !== undefined) {
            white_time_display = wt;
            white_time_ts = now;
        }
        if (bt !== null && bt !== undefined) {
            black_time_display = bt;
            black_time_ts = now;
        }
    }

    function start_clock_tick() {
        if (clock_interval) return;
        clock_interval = setInterval(() => {
            if (!match_data || match_data.status !== 'active') return;
            // Only tick if timed
            if (white_time_display === null && black_time_display === null) return;

            const turn = chess.turn() === 'w' ? 'white' : 'black';
            const now = Date.now();

            if (turn === 'white' && white_time_display !== null && white_time_ts > 0) {
                const elapsed = (now - white_time_ts) / 1000;
                white_time_display = Math.max(0, white_time_display - elapsed);
                white_time_ts = now;
            } else if (turn === 'black' && black_time_display !== null && black_time_ts > 0) {
                const elapsed = (now - black_time_ts) / 1000;
                black_time_display = Math.max(0, black_time_display - elapsed);
                black_time_ts = now;
            }
        }, 100);
    }

    function stop_clock_tick() {
        if (clock_interval) { clearInterval(clock_interval); clock_interval = null; }
    }

    // ──────────────────────────────────────────────
    // WebSocket message handling
    // ──────────────────────────────────────────────

    async function handle_ws_message(data: any) {
        console.log(">> WS INCOMING:", data);
        const event = data.event;

        if (event === 'move') {
            console.log(">> EVENT: MOVE DETECTED");
            console.log(">> MOVE DATA:", { uci: data.uci, fen: data.fen, pgn: data.pgn });
            
            pending_move = null;

            // 1. Try to load full PGN if the server provides it
            if (data.pgn) {
                console.log(">> USING PGN LOGIC");
                load_pgn_safe(data.pgn);
            } 
            // 2. Fallback: If the server sends a FEN string instead
            else if (data.fen) {
                console.log(">> USING FEN LOGIC");
                const success = chess.load(data.fen);
                console.log(">> FEN LOAD SUCCESS:", success);
                sync_board_from_chess();
            } 
            // 3. Fallback: If the server just echoes the raw UCI move (e.g., "e2e4")
            else if (data.uci) {
                console.log(">> USING RAW UCI LOGIC");
                try {
                    const moveResult = chess.move({ 
                        from: data.uci.slice(0, 2), 
                        to: data.uci.slice(2, 4), 
                        promotion: data.uci.length > 4 ? data.uci[4] : 'q' 
                    });
                    console.log(">> LOCAL CHESS.JS MOVE RESULT:", moveResult);
                    sync_board_from_chess();
                } catch (e) {
                    console.error(">> Local chess.js engine rejected the server move:", e);
                }
            } else {
                console.error(">> FATAL: Move event received with no PGN, FEN, or UCI data.");
            }

            // Update clocks from server
            sync_clocks_from_server(data.white_time_left ?? null, data.black_time_left ?? null);

            // Update last move highlight (the green squares)
            if (data.uci && data.uci.length >= 4) {
                cg_last_move = [data.uci.slice(0, 2), data.uci.slice(2, 4)];
            }

            // Update match status
            if (data.match_status && match_data) {
                match_data = { ...match_data, status: data.match_status };
                if (data.match_status === 'active') {
                    start_clock_tick();
                }
            }
            
            console.log(">> CALLING sync_board_from_chess() AFTER MOVE");
            sync_board_from_chess(); 
            console.log(">> NEW STATE: is_my_turn =", is_my_turn, " | fen =", cg_fen);
        }

        if (event === 'player_connected') {
            console.log(">> EVENT: PLAYER_CONNECTED:", data.user_id, data.name);
            seen_connections.add(data.user_id as string);
            
            if (data.name) {
                player_names[data.user_id] = data.name;
                console.log(">> UPDATED PLAYER NAMES:", player_names);
            }

            if (match_data?.status === 'pending') {
                try {
                    const res = await api<Match>(`/match/${match_id}`);
                    match_data = res.data;
                    if (match_data.white_player_id) seen_connections.add(match_data.white_player_id);
                    if (match_data.black_player_id) seen_connections.add(match_data.black_player_id);
                } catch {}
            }

            const white_id = match_data?.white_player_id;
            const black_id = match_data?.black_player_id;
            const seats_filled = !!white_id && !!black_id;
            const both_seen = seats_filled && seen_connections.has(white_id!) && seen_connections.has(black_id!);

            console.log(">> CONNECTION STATE:", { seats_filled, both_seen, white_id, black_id });

            if (both_seen) {
                both_connected = true;
                if (match_data?.status === 'starting' || match_data?.status === 'pending') {
                    match_data = { ...match_data, status: 'active' };
                }
            }
            sync_board_from_chess(); 
        }

        if (event === 'player_disconnected') {
            if (data.user_id !== $current_user?.id) {
                both_connected = false;
                if (!game_over) status_msg = 'OPPONENT DISCONNECTED';
            }
        }

        if (event === 'game_over') {
            game_over = {
                reason: data.reason,
                winner_id: data.winner_id,
                w_change: data.white_rating_change ?? null,
                b_change: data.black_rating_change ?? null
            };
            if (match_data) match_data = { ...match_data, status: 'completed' };
            stop_clock_tick();
            is_my_turn = false;
            dests = new Map();
        }

        if (event === 'error') {
            if (pending_move) {
                if (match_data?.pgn_moves !== undefined) {
                    load_pgn_safe(match_data.pgn_moves || '');
                }
                pending_move = null;
            }
            status_msg = `ERR: ${data.message}`;
        }
    }

    // ──────────────────────────────────────────────
    // WebSocket connection
    // ──────────────────────────────────────────────

    function connect_websocket() {
        console.log(">> INITIATING WEBSOCKET CONNECTION");
        const url = ws_url(match_id);
        
        socket = new WebSocket(url);

        socket.onopen = () => {
            console.log(">> WS OPENED SUCCESSFULLY");
            ws_connected.set(true);
        };

        socket.onmessage = (ev) => {
            try {
                const data = JSON.parse(ev.data);
                handle_ws_message(data);
            } catch (e) {
                console.error(">> FAILED TO PARSE WS MESSAGE:", ev.data);
            }
        };

        socket.onclose = () => {
            console.warn(">> WS CLOSED");
            ws_connected.set(false);
            stop_clock_tick();
        };

        socket.onerror = (err) => {
            console.error(">> WS ERROR:", err);
            ws_connected.set(false);
        };
    }
    
    // ──────────────────────────────────────────────
    // Move sending — NO optimistic apply
    // We send to server and wait for the echo back
    // ──────────────────────────────────────────────
    function send_move(from: string, to: string) {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            console.error(">> ABORTING: WebSocket is not open.");
            return;
        }
        if (!is_my_turn) {
            console.error(">> ABORTING: Not your turn.");
            return;
        }

        // Detect promotion: pawn reaching last rank
        let promo: string | undefined;
        const piece = chess.get(from as any);
        if (piece?.type === 'p') {
            const dest_rank = to[1];
            if ((piece.color === 'w' && dest_rank === '8') || (piece.color === 'b' && dest_rank === '1')) {
                promo = 'q'; // Always queen for now; TODO: promotion picker
            }
        }

        // Build a raw, standard JavaScript string
        const safe_uci = `${from}${to}${promo ?? ''}`;
        
        pending_move = { from, to, promo };
        is_my_turn = false;
        dests = new Map();

        // Build a pure, unproxied JavaScript object
        const raw_payload = {
            event: "move",
            uci: safe_uci
        };

        const json_payload = JSON.stringify(raw_payload);
        
        console.log(">> 🚀 FIRING PURE PAYLOAD TO BACKEND:", json_payload);
        
        try {
            socket.send(json_payload);
            status_msg = "TRANSMITTING MOVE...";
        } catch (e) {
            console.error(">> FATAL: socket.send() crashed locally!", e);
        }
    }

    // ──────────────────────────────────────────────
    // Waiting room: poll until opponent joins (PENDING → STARTING)
    // ──────────────────────────────────────────────

    function start_waiting_poll() {
        if (poll_interval) return;
        poll_interval = setInterval(async () => {
            try {
                const res = await api<Match>(`/match/${match_id}`);
                const m = res.data;
                if (m.status === 'starting' || m.status === 'active') {
                    stop_waiting_poll();
                    match_data = m;
                    // Now we can connect WebSocket — opponent has joined
                    if (!socket || socket.readyState > WebSocket.OPEN) {
                        connect_websocket();
                    }
                }
            } catch {}
        }, 2000);
    }

    function stop_waiting_poll() {
        if (poll_interval) { clearInterval(poll_interval); poll_interval = null; }
    }

    // ──────────────────────────────────────────────
    // Actions
    // ──────────────────────────────────────────────

    async function resign() {
        try {
            await api(`/match/${match_id}/resign`, { method: 'POST' });
        } catch (e: any) {
            status_msg = `ERR: ${e.message}`;
        }
        confirming_resign = false;
    }

    async function offer_draw() {
        try {
            await api(`/match/${match_id}/draw`, { method: 'POST' });
        } catch (e: any) {
            status_msg = `ERR: ${e.message}`;
        }
        confirming_draw = false;
    }

    // ──────────────────────────────────────────────
    // Lifecycle
    // ──────────────────────────────────────────────

    onMount(async () => {
        if (!$is_authenticated) { goto('/'); return; }

        try {
            const res = await api<Match>(`/match/${match_id}`);
            match_data = res.data;
            active_match.set(match_data);

            // Determine color
            if (!$my_color) {
                if (match_data.white_player_id === $current_user?.id) my_color.set('white');
                else if (match_data.black_player_id === $current_user?.id) my_color.set('black');
            }
            cg_orientation = $my_color ?? 'white';

            // Load any existing moves (reconnection scenario)
            if (match_data.pgn_moves) load_pgn_safe(match_data.pgn_moves);
            else sync_board_from_chess();

            // Sync clocks
            sync_clocks_from_server(
                match_data.white_time_left ?? null,
                match_data.black_time_left ?? null
            );

            if (match_data.status === 'pending') {
                // Creator waiting — connect WS now, board stays blurred.
                // When opponent joins + connects, we'll get their PLAYER_CONNECTED
                // event. At that point match_data will have both IDs and we unblur.
                status_msg = 'WAITING FOR OPPONENT...';
                connect_websocket();
            } else if (match_data.status === 'starting') {
                // Both seats filled — opponent has joined via HTTP.
                // Connect WS; once we receive PLAYER_CONNECTED events for both
                // user IDs we'll unlock. Pre-seed our own ID since we're about to fire.
                if (match_data.white_player_id) seen_connections.add(match_data.white_player_id);
                if (match_data.black_player_id) seen_connections.add(match_data.black_player_id);
                both_connected = true;
                match_data = { ...match_data, status: 'active' };
                connect_websocket();
            } else if (match_data.status === 'active') {
                // Reconnecting to live game
                both_connected = true;
                connect_websocket();
                start_clock_tick();
            } else {
                // completed/canceled — just show board, no WS
                status_msg = match_data.status.toUpperCase();
            }

        } catch (e: any) {
            status_msg = `LOAD FAILED: ${e.message}`;
        }
    });

    onDestroy(() => {
        socket?.close();
        stop_clock_tick();
        stop_waiting_poll();
        ws_connected.set(false);
    });

    // ──────────────────────────────────────────────
    // Derived Reactive State
    // ──────────────────────────────────────────────

    const white_low = $derived(white_time_display !== null && white_time_display < 30);
    const black_low = $derived(black_time_display !== null && black_time_display < 30);
    const player_side = $derived($my_color ?? 'white');
    const opponent_side = $derived(player_side === 'white' ? 'black' : 'white');
    const is_timed = $derived(match_data?.time_control?.toLowerCase() !== 'untimed' && white_time_display !== null);
    const is_waiting = $derived(
        match_data?.status === 'pending' || match_data?.status === 'starting'
    );

    // --- THE FIX: MAKE THE CONFIG REACTIVE ---
    // By deriving this, Svelte forces the Chessground component to fully update 
    // every time `is_waiting`, `$my_color`, or `dests` changes.
    const board_config = $derived({
        movable: {
            color: is_waiting ? undefined : ($my_color ?? undefined),
            dests: dests,
            free: false
        },
        draggable: { enabled: !is_waiting },
        animation: { enabled: true, duration: 180 },
        highlight: { lastMove: true, check: true },
        premovable: { enabled: false },
        events: {
            move: (orig: string, dest: string) => {
                send_move(orig, dest);
            }
        }
    });
    
</script>

<div class="game-root">
    <!-- HUD Top bar -->
    <div class="hud-bar">
        <div class="hud-left">
            <a href="/lobby" class="back-link">← LOBBY</a>
            <span class="match-id-label">MATCH: {match_id.slice(0,8).toUpperCase()}</span>
            {#if match_data}
                <span class="tc-label">{match_data.time_control.toUpperCase()}</span>
                <span class="mode-label" class:rated={match_data.is_rated}>
                    {match_data.is_rated ? 'RATED' : 'CASUAL'}
                </span>
            {/if}
        </div>
        <div class="hud-center">
            <span class="status-label"
                class:my-turn={is_my_turn}
                class:check={status_msg === 'CHECK!'}
                class:waiting={is_waiting}
            >
                {status_msg}
            </span>
        </div>
        <div class="hud-right">
            {#if is_waiting}
                <span class="link-indicator waiting-pulse">◈ WAITING</span>
            {:else}
                <span class="link-indicator" class:online={$ws_connected}>
                    {$ws_connected ? '⬤ LINK UP' : '⬤ LINKING...'}
                </span>
            {/if}
        </div>
    </div>

    <!-- Main game layout -->
    <div class="game-layout">

        <!-- Opponent player strip (top) -->
        <div class="player-strip opponent-strip">
            <div class="player-info">
                <span class="color-dot" class:white-dot={opponent_side === 'white'} class:black-dot={opponent_side === 'black'}></span>
                <span class="player-label">{opponent_side.toUpperCase()}</span>
            </div>
            {#if is_timed}
                <div class="clock" class:low={opponent_side === 'white' ? white_low : black_low}
                    class:active-clock={!is_my_turn && both_connected && match_data?.status === 'active'}>
                    {opponent_side === 'white' ? format_clock(white_time_display) : format_clock(black_time_display)}
                </div>
            {:else}
                <div class="clock infinity">∞</div>
            {/if}
        </div>

        <!-- Board -->
        <div class="board-container" class:blurred={is_waiting}>
                    <div class="board-frame">
                        <Chessground
                            bind:this={cg_api}
                            fen={cg_fen}
                            orientation={cg_orientation}
                            lastMove={cg_last_move}
                            config={board_config}
                        />
                    </div>
                    {#if is_waiting}
                <div class="waiting-overlay">
                    <div class="waiting-icon">◈</div>
                    <div class="waiting-text">WAITING FOR OPPONENT</div>
                    <div class="waiting-sub">Share the match ID to invite someone</div>
                    <button class="copy-btn" onclick={() => navigator.clipboard.writeText(match_id)}>
                        COPY: {match_id.slice(0,8).toUpperCase()}...
                    </button>
                </div>
            {/if}
        </div>

        <!-- My player strip (bottom) -->
        <div class="player-strip my-strip">
            <div class="player-info">
                <span class="color-dot" class:white-dot={player_side === 'white'} class:black-dot={player_side === 'black'}></span>
                <span class="player-label">{$current_user?.name ?? player_side.toUpperCase()}</span>
            </div>
            {#if is_timed}
                <div class="clock my-clock" class:low={player_side === 'white' ? white_low : black_low}
                    class:active-clock={is_my_turn}>
                    {player_side === 'white' ? format_clock(white_time_display) : format_clock(black_time_display)}
                </div>
            {:else}
                <div class="clock infinity">∞</div>
            {/if}
        </div>
    </div>

    <!-- Right sidebar: move history + controls -->
    <div class="sidebar">
        <div class="sidebar-section">
            <div class="sidebar-label">NOTATION</div>
            <div class="move-history">
                {#each move_history as move, i}
                    {#if i % 2 === 0}
                        <div class="move-pair">
                            <span class="move-num">{Math.floor(i/2)+1}.</span>
                            <span class="move-san white-move">{move}</span>
                            {#if move_history[i+1]}
                                <span class="move-san black-move">{move_history[i+1]}</span>
                            {/if}
                        </div>
                    {/if}
                {/each}
                {#if move_history.length === 0}
                    <p class="no-moves">NO MOVES YET</p>
                {/if}
            </div>
        </div>

        <div class="sidebar-section controls">
            {#if !game_over && match_data?.status !== 'pending' && match_data?.status !== 'completed' && match_data?.status !== 'canceled'}
                {#if !confirming_resign && !confirming_draw}
                    <button class="ctrl-btn resign-btn" onclick={() => confirming_resign = true}>RESIGN</button>
                    <button class="ctrl-btn draw-btn" onclick={() => confirming_draw = true}>OFFER DRAW</button>
                {:else if confirming_resign}
                    <p class="confirm-label">CONFIRM RESIGN?</p>
                    <div class="confirm-row">
                        <button class="ctrl-btn danger-btn" onclick={resign}>YES</button>
                        <button class="ctrl-btn" onclick={() => confirming_resign = false}>NO</button>
                    </div>
                {:else if confirming_draw}
                    <p class="confirm-label">OFFER DRAW?</p>
                    <div class="confirm-row">
                        <button class="ctrl-btn draw-btn" onclick={offer_draw}>OFFER</button>
                        <button class="ctrl-btn" onclick={() => confirming_draw = false}>CANCEL</button>
                    </div>
                {/if}
            {:else if match_data?.status === 'pending'}
                <!-- Waiting for opponent — can cancel -->
                <button class="ctrl-btn resign-btn" onclick={async () => {
                    try { await api(`/match/${match_id}`, { method: 'DELETE' }); } catch {}
                    goto('/lobby');
                }}>CANCEL MATCH</button>
            {:else}
                <button class="ctrl-btn" onclick={() => goto('/lobby')}>BACK TO LOBBY</button>
            {/if}
        </div>
    </div>

    <!-- Game over overlay -->
    {#if game_over}
    <div class="game-over-overlay">
        <div class="game-over-card">
            <div class="go-header">[ GAME OVER ]</div>
            <div class="go-reason">{game_over.reason.replace(/_/g, ' ').toUpperCase()}</div>
            {#if game_over.winner_id}
                <div class="go-result" class:victory={game_over.winner_id === $current_user?.id}>
                    {game_over.winner_id === $current_user?.id ? '▲ VICTORY' : '▼ DEFEAT'}
                </div>
            {:else}
                <div class="go-result draw-result">═ DRAW ═</div>
            {/if}
            {#if game_over.w_change !== null && game_over.w_change !== undefined}
                <div class="go-ratings">
                    <div class="rating-row">
                        <span class="rating-side">♔ WHITE</span>
                        <span class="rating-delta" class:pos={game_over.w_change! >= 0}>
                            {game_over.w_change! >= 0 ? '+' : ''}{game_over.w_change}
                        </span>
                    </div>
                    <div class="rating-row">
                        <span class="rating-side">♚ BLACK</span>
                        <span class="rating-delta" class:pos={(game_over.b_change ?? 0) >= 0}>
                            {(game_over.b_change ?? 0) >= 0 ? '+' : ''}{game_over.b_change}
                        </span>
                    </div>
                </div>
            {/if}
            <button class="ctrl-btn go-lobby-btn" onclick={() => goto('/lobby')}>RETURN TO LOBBY</button>
        </div>
    </div>
    {/if}
</div>

<style>
    .game-root {
        width: 100vw;
        height: 100vh;
        display: grid;
        grid-template-columns: 1fr 240px;
        grid-template-rows: 44px 1fr;
        overflow: hidden;
        background: var(--bg);
    }

    /* HUD */
    .hud-bar {
        grid-column: 1 / -1;
        grid-row: 1;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 1.5rem;
        border-bottom: 1px solid var(--border);
        background: rgba(0,229,255,0.02);
        z-index: 10;
    }

    .hud-left, .hud-right {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        min-width: 180px;
    }

    .hud-right { justify-content: flex-end; }
    .hud-center { flex: 1; display: flex; justify-content: center; }

    .back-link {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        text-decoration: none;
        transition: color 0.15s;
    }
    .back-link:hover { color: var(--cyan); }

    .match-id-label {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--text-muted);
        letter-spacing: 0.05em;
        opacity: 0.4;
    }

    .tc-label {
        font-family: var(--font-display);
        font-size: 0.6rem;
        color: var(--text-muted);
        letter-spacing: 0.1em;
    }

    .mode-label {
        font-family: var(--font-mono);
        font-size: 0.5rem;
        letter-spacing: 0.1em;
        padding: 2px 6px;
        border: 1px solid var(--border);
        color: var(--text-muted);
    }
    .mode-label.rated {
        border-color: var(--amber);
        color: var(--amber);
    }

    .status-label {
        font-family: var(--font-display);
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.2em;
        color: var(--text-muted);
        transition: color 0.3s, text-shadow 0.3s;
    }
    .status-label.my-turn {
        color: var(--cyan);
        text-shadow: var(--cyan-glow);
    }
    .status-label.check {
        color: var(--red);
        text-shadow: 0 0 20px rgba(255,23,68,0.5);
    }
    .status-label.waiting {
        color: var(--amber);
        animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse { 50% { opacity: 0.4; } }

    .link-indicator {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        color: var(--red);
    }
    .link-indicator.online { color: var(--green); }
    .link-indicator.waiting-pulse {
        color: var(--amber);
        animation: pulse 1.2s step-end infinite;
    }

    /* Game layout */
    .game-layout {
        grid-column: 1;
        grid-row: 2;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1rem 0 1rem 1.5rem;
        gap: 0.5rem;
    }

    /* Player strips */
    .player-strip {
        width: 100%;
        max-width: 560px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 10px;
        background: var(--surface);
        border: 1px solid var(--border);
    }

    .player-info {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .color-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        border: 1px solid var(--border);
    }
    .white-dot { background: #e0e0e0; border-color: #999; }
    .black-dot { background: #222; border-color: #555; }

    .player-label {
        font-family: var(--font-mono);
        font-size: 0.65rem;
        letter-spacing: 0.1em;
        color: var(--text-muted);
    }

    .clock {
        font-family: var(--font-display);
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        color: var(--text-muted);
        transition: color 0.3s, text-shadow 0.3s;
        min-width: 70px;
        text-align: right;
    }
    .clock.active-clock {
        color: var(--text-primary);
    }
    .clock.low {
        color: var(--red);
        text-shadow: 0 0 12px rgba(255,23,68,0.4);
        animation: pulse 0.6s ease-in-out infinite;
    }
    .clock.infinity {
        color: var(--text-muted);
        font-size: 1.6rem;
    }

    /* Board */
    .board-container {
        position: relative;
        max-width: 560px;
        width: 100%;
        aspect-ratio: 1;
    }

    .board-frame {
        width: 100%;
        height: 100%;
        border: 1px solid var(--border);
    }

    .board-container.blurred .board-frame {
        filter: blur(6px);
        opacity: 0.4;
        pointer-events: none;
    }

    /* Waiting overlay */
    .waiting-overlay {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        z-index: 5;
    }

    .waiting-icon {
        font-size: 3rem;
        color: var(--amber);
        animation: pulse 1.5s ease-in-out infinite;
    }

    .waiting-text {
        font-family: var(--font-display);
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.2em;
        color: var(--amber);
    }

    .waiting-sub {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        color: var(--text-muted);
    }

    .copy-btn {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        background: transparent;
        border: 1px solid var(--amber);
        color: var(--amber);
        padding: 6px 14px;
        cursor: pointer;
        transition: background 0.15s;
        margin-top: 0.5rem;
    }
    .copy-btn:hover { background: rgba(255,171,0,0.1); }

    /* Sidebar */
    .sidebar {
        grid-column: 2;
        grid-row: 2;
        border-left: 1px solid var(--border);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .sidebar-section {
        display: flex;
        flex-direction: column;
    }

    .sidebar-section:first-child {
        flex: 1;
        overflow: hidden;
    }

    .sidebar-label {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        letter-spacing: 0.2em;
        color: var(--text-muted);
        padding: 10px 14px;
        border-bottom: 1px solid var(--border);
        background: rgba(0,229,255,0.02);
        flex-shrink: 0;
    }

    .move-history {
        flex: 1;
        overflow-y: auto;
        padding: 8px 14px;
    }

    .move-history::-webkit-scrollbar { width: 3px; }
    .move-history::-webkit-scrollbar-thumb { background: var(--border); }

    .move-pair {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 3px 0;
        font-family: var(--font-mono);
        font-size: 0.68rem;
    }

    .move-num {
        color: var(--text-muted);
        width: 20px;
        flex-shrink: 0;
        font-size: 0.55rem;
    }

    .move-san {
        padding: 1px 5px;
        min-width: 48px;
    }

    .white-move {
        color: var(--text-primary);
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.06);
    }

    .black-move {
        color: #6080a0;
        background: rgba(0,0,0,0.2);
        border: 1px solid rgba(0,0,0,0.3);
    }

    .no-moves {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--text-muted);
        letter-spacing: 0.1em;
        padding-top: 6px;
        opacity: 0.4;
    }

    /* Controls */
    .controls {
        padding: 14px;
        border-top: 1px solid var(--border);
        gap: 8px;
        flex-shrink: 0;
    }

    .ctrl-btn {
        width: 100%;
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.12em;
        background: transparent;
        border: 1px solid var(--border);
        color: var(--text-muted);
        padding: 8px;
        cursor: pointer;
        transition: all 0.15s;
        margin-bottom: 6px;
        display: block;
    }
    .ctrl-btn:last-child { margin-bottom: 0; }
    .ctrl-btn:hover { border-color: var(--cyan); color: var(--cyan); }

    .resign-btn { border-color: var(--red); color: var(--red); }
    .resign-btn:hover { background: var(--red-dim); }
    .draw-btn { border-color: var(--amber); color: var(--amber); }
    .draw-btn:hover { background: rgba(255,171,0,0.08); }
    .danger-btn { border-color: var(--red); color: var(--red); background: var(--red-dim); }

    .confirm-label {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--text-muted);
        letter-spacing: 0.1em;
        margin-bottom: 6px;
        text-align: center;
    }

    .confirm-row {
        display: flex;
        gap: 6px;
    }
    .confirm-row .ctrl-btn { margin-bottom: 0; }

    /* Game over overlay */
    .game-over-overlay {
        position: fixed;
        inset: 0;
        background: rgba(2, 4, 8, 0.85);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 100;
        backdrop-filter: blur(4px);
    }

    .game-over-card {
        background: var(--surface);
        border: 1px solid var(--border);
        padding: 0;
        width: 320px;
        text-align: center;
        box-shadow: 0 0 60px rgba(0,229,255,0.1);
        position: relative;
    }

    .game-over-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--cyan), transparent);
    }

    .go-header {
        font-family: var(--font-display);
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.25em;
        color: var(--text-muted);
        padding: 14px 20px 8px;
        border-bottom: 1px solid var(--border);
    }

    .go-reason {
        font-family: var(--font-mono);
        font-size: 0.65rem;
        letter-spacing: 0.15em;
        color: var(--text-muted);
        padding: 12px 20px 0;
    }

    .go-result {
        font-family: var(--font-display);
        font-size: 1.5rem;
        font-weight: 900;
        letter-spacing: 0.1em;
        padding: 12px 20px;
    }

    .go-result.victory { color: var(--cyan); text-shadow: var(--cyan-glow); }
    .go-result:not(.victory):not(.draw-result) { color: var(--red); }
    .go-result.draw-result { color: var(--amber); }

    .go-ratings {
        padding: 0 20px 16px;
        border-bottom: 1px solid var(--border);
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .rating-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .rating-side {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        color: var(--text-muted);
        letter-spacing: 0.08em;
    }

    .rating-delta {
        font-family: var(--font-display);
        font-size: 0.85rem;
        font-weight: 700;
        color: var(--red);
    }
    .rating-delta.pos { color: var(--green); }

    .go-lobby-btn {
        display: block;
        margin: 14px 20px;
        width: calc(100% - 40px);
    }
</style>