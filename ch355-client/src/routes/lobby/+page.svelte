<!-- src/routes/lobby/+page.svelte -->
<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { goto } from '$app/navigation';
    import { is_authenticated, current_user, open_matches, my_color } from '$lib/stores';
    import { api } from '$lib/api';
    import { time_control_label } from '$lib/chess_utils';
    import type { Match } from '$lib/stores';

    let loading = $state(false);
    let error_msg = $state('');
    let creating = $state(false);
    let joining_id = $state<string | null>(null);
    let my_active_match = $state<Match | null>(null);

    // Create match form
    let form_time = $state('10+0');
    let form_rated = $state(true);
    let form_private = $state(false);
    let form_color = $state('random');

    let poll_interval: ReturnType<typeof setInterval>;

    onMount(() => {
        if (!$is_authenticated) { goto('/'); return; }
        fetch_matches();
        poll_interval = setInterval(fetch_matches, 3000);
    });

    onDestroy(() => clearInterval(poll_interval));

    async function fetch_matches() {
        try {
            const res = await api<Match[]>('/match/open');
            open_matches.set(res.data);
        } catch {}

        // Also check if this user has an active match already
        // (Backend blocks creating two matches, but user may have navigated away)
        // We do this by checking open matches for our user ID, plus query may fail silently
        // Actually the backend /match/open filters us out; we need to check separately.
        // We'll track it in state after create/join.
    }

    async function create_match() {
        creating = true;
        error_msg = '';
        try {
            const res = await api<Match>('/match/create', {
                method: 'POST',
                body: JSON.stringify({
                    play_as: form_color,
                    is_rated: form_rated,
                    is_private: form_private,
                    time_control: form_time
                })
            });
            const match = res.data;
            // Set color based on which slot we occupy
            if (match.white_player_id === $current_user?.id) my_color.set('white');
            else my_color.set('black');
            // Navigate to game page — it will handle the PENDING waiting state
            goto(`/game/${match.id}`);
        } catch (e: any) {
            error_msg = e.message;
        } finally {
            creating = false;
        }
    }

    async function join_match(match_id: string) {
        joining_id = match_id;
        error_msg = '';
        try {
            const res = await api<Match>(`/match/${match_id}/join`, { method: 'POST' });
            const match = res.data;
            // After joining, status is STARTING; determine color
            if (match.white_player_id === $current_user?.id) my_color.set('white');
            else my_color.set('black');
            goto(`/game/${match.id}`);
        } catch (e: any) {
            error_msg = e.message;
        } finally {
            joining_id = null;
        }
    }

    const TIME_PRESETS = ['1+0', '3+0', '3+2', '5+0', '10+0', '15+10', '30+0', 'untimed'];
</script>

<div class="lobby-page">
    <div class="lobby-grid">

        <!-- Left: Create match panel -->
        <div class="panel create-panel">
            <div class="panel-header">
                <span class="panel-tag">INIT</span>
                <h2 class="panel-title">NEW MATCH</h2>
            </div>
            <div class="panel-body">

                <div class="form-group">
                    <span class="form-label">TIME CONTROL</span>
                    <div class="preset-grid">
                        {#each TIME_PRESETS as preset}
                            <button
                                class="preset-btn"
                                class:active={form_time === preset}
                                onclick={() => form_time = preset}
                            >
                                {preset === 'untimed' ? '∞' : preset}
                            </button>
                        {/each}
                    </div>
                    <div class="form-hint">{time_control_label(form_time)}</div>
                </div>

                <div class="form-group">
                    <span class="form-label">PLAY AS</span>
                    <div class="color-picker">
                        {#each ['white', 'random', 'black'] as c}
                            <button
                                class="color-btn"
                                class:active={form_color === c}
                                onclick={() => form_color = c}
                            >
                                {#if c === 'white'}♔{:else if c === 'black'}♚{:else}⚄{/if}
                                {c.toUpperCase()}
                            </button>
                        {/each}
                    </div>
                </div>

                <div class="form-group">
                    <div class="toggle-row">
                        <span class="form-label">RATED MATCH</span>
                        <button class="toggle-btn" class:on={form_rated} onclick={() => form_rated = !form_rated}>
                            {form_rated ? 'ON' : 'OFF'}
                        </button>
                    </div>
                    <div class="toggle-row">
                        <span class="form-label">PRIVATE LOBBY</span>
                        <button class="toggle-btn" class:on={form_private} onclick={() => form_private = !form_private}>
                            {form_private ? 'ON' : 'OFF'}
                        </button>
                    </div>
                </div>

                {#if error_msg}
                    <p class="error-line">ERR // {error_msg}</p>
                {/if}

                <button class="cta-btn" onclick={create_match} disabled={creating}>
                    {creating ? 'ALLOCATING...' : '[ LAUNCH MATCH ]'}
                </button>
            </div>
        </div>

        <!-- Right: Open matches list -->
        <div class="panel matches-panel">
            <div class="panel-header">
                <span class="panel-tag">OPEN</span>
                <h2 class="panel-title">MATCH QUEUE</h2>
                <span class="match-count">{$open_matches.length} WAITING</span>
            </div>
            <div class="matches-list">
                {#if $open_matches.length === 0}
                    <div class="empty-state">
                        <div class="empty-icon">◈</div>
                        <p class="empty-text">NO ACTIVE LOBBIES</p>
                        <p class="empty-sub">BE THE FIRST TO INITIALIZE A MATCH</p>
                    </div>
                {:else}
                    {#each $open_matches as match (match.id)}
                        <div class="match-row">
                            <div class="match-info">
                                <div class="match-tc">{match.time_control.toUpperCase()}</div>
                                <div class="match-meta">
                                    <span class="meta-badge" class:rated={match.is_rated}>
                                        {match.is_rated ? 'RATED' : 'CASUAL'}
                                    </span>
                                    <span class="meta-badge">
                                        {match.white_player_id ? '♔ NEEDS BLACK' : '♚ NEEDS WHITE'}
                                    </span>
                                    {#if match.is_private}
                                        <span class="meta-badge private-badge">PRIVATE</span>
                                    {/if}
                                </div>
                                <div class="match-id">ID: {match.id.slice(0, 8).toUpperCase()}…</div>
                            </div>
                            <button
                                class="join-btn"
                                onclick={() => join_match(match.id)}
                                disabled={joining_id === match.id}
                            >
                                {joining_id === match.id ? '...' : 'JOIN'}
                            </button>
                        </div>
                    {/each}
                {/if}
            </div>
        </div>

    </div>

    <!-- User stats bar -->
    {#if $current_user}
    <div class="stats-bar">
        <div class="stat-block">
            <span class="stat-val">{$current_user.elo_rating}</span>
            <span class="stat-lbl">ELO</span>
        </div>
        <div class="stat-sep">|</div>
        <div class="stat-block">
            <span class="stat-val">{$current_user.matches_played}</span>
            <span class="stat-lbl">PLAYED</span>
        </div>
        <div class="stat-sep">|</div>
        <div class="stat-block">
            <span class="stat-val">{$current_user.matches_won}</span>
            <span class="stat-lbl">W</span>
        </div>
        <div class="stat-sep">/</div>
        <div class="stat-block">
            <span class="stat-val">{$current_user.matches_drawn}</span>
            <span class="stat-lbl">D</span>
        </div>
        <div class="stat-sep">/</div>
        <div class="stat-block">
            <span class="stat-val">{$current_user.matches_lost}</span>
            <span class="stat-lbl">L</span>
        </div>
        <div class="stat-sep">|</div>
        <div class="stat-block">
            <span class="stat-val">{$current_user.conduct_score ?? 100}</span>
            <span class="stat-lbl">CONDUCT</span>
        </div>
        <div class="stat-sep">|</div>
        <div class="stat-block">
            <span class="stat-val">{$current_user.name}</span>
            <span class="stat-lbl">HANDLE</span>
        </div>
    </div>
    {/if}
</div>

<style>
    .lobby-page {
        padding: 2rem;
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
        max-width: 1100px;
        margin: 0 auto;
    }

    .lobby-grid {
        display: grid;
        grid-template-columns: 340px 1fr;
        gap: 1.5rem;
        align-items: start;
    }

    .panel {
        background: var(--surface);
        border: 1px solid var(--border);
        position: relative;
    }

    .panel::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--cyan), transparent);
        opacity: 0.5;
    }

    .panel-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        background: rgba(0, 229, 255, 0.03);
    }

    .panel-tag {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--cyan);
        background: var(--cyan-dim);
        padding: 2px 6px;
        letter-spacing: 0.1em;
    }

    .panel-title {
        font-family: var(--font-display);
        font-size: 0.8rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: 0.15em;
        flex: 1;
    }

    .match-count {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        color: var(--amber);
        letter-spacing: 0.1em;
    }

    .panel-body {
        padding: 1.25rem;
    }

    .form-group {
        margin-bottom: 1.25rem;
    }

    .form-label {
        display: block;
        font-family: var(--font-mono);
        font-size: 0.6rem;
        color: var(--text-muted);
        letter-spacing: 0.15em;
        margin-bottom: 0.5rem;
    }

    .preset-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 4px;
    }

    .preset-btn {
        font-family: var(--font-mono);
        font-size: 0.65rem;
        letter-spacing: 0.05em;
        background: var(--surface-2);
        border: 1px solid var(--border);
        color: var(--text-muted);
        padding: 6px 4px;
        cursor: pointer;
        transition: all 0.15s;
        text-align: center;
    }
    .preset-btn:hover, .preset-btn.active {
        border-color: var(--cyan);
        color: var(--cyan);
        background: var(--cyan-dim);
    }

    .form-hint {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--text-muted);
        letter-spacing: 0.1em;
        margin-top: 4px;
    }

    .color-picker {
        display: flex;
        gap: 4px;
    }

    .color-btn {
        flex: 1;
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.08em;
        background: var(--surface-2);
        border: 1px solid var(--border);
        color: var(--text-muted);
        padding: 8px 4px;
        cursor: pointer;
        transition: all 0.15s;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
    }
    .color-btn:hover, .color-btn.active {
        border-color: var(--cyan);
        color: var(--cyan);
        background: var(--cyan-dim);
    }

    .toggle-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }
    .toggle-row .form-label { margin: 0; }

    .toggle-btn {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        background: var(--surface-2);
        border: 1px solid var(--border);
        color: var(--text-muted);
        padding: 4px 10px;
        cursor: pointer;
        transition: all 0.15s;
        min-width: 48px;
    }
    .toggle-btn.on {
        border-color: var(--green);
        color: var(--green);
        background: rgba(0, 230, 118, 0.08);
    }

    .cta-btn {
        width: 100%;
        font-family: var(--font-display);
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        background: transparent;
        border: 1px solid var(--cyan);
        color: var(--cyan);
        padding: 14px;
        cursor: pointer;
        transition: all 0.2s;
        margin-top: 0.5rem;
        position: relative;
        overflow: hidden;
    }
    .cta-btn:hover { box-shadow: var(--cyan-glow); background: var(--cyan-dim); }
    .cta-btn:disabled { opacity: 0.4; cursor: not-allowed; }

    .error-line {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        color: var(--red);
        letter-spacing: 0.1em;
        margin-bottom: 0.5rem;
    }

    /* Matches list */
    .matches-list {
        min-height: 300px;
        max-height: 520px;
        overflow-y: auto;
    }
    .matches-list::-webkit-scrollbar { width: 4px; }
    .matches-list::-webkit-scrollbar-thumb { background: var(--border); }

    .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 4rem 2rem;
        gap: 0.5rem;
        color: var(--text-muted);
    }

    .empty-icon { font-size: 2rem; color: var(--border); margin-bottom: 0.5rem; }
    .empty-text {
        font-family: var(--font-display);
        font-size: 0.75rem;
        letter-spacing: 0.2em;
    }
    .empty-sub {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.12em;
    }

    .match-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 16px;
        border-bottom: 1px solid rgba(0, 229, 255, 0.06);
        transition: background 0.15s;
    }
    .match-row:hover { background: rgba(0, 229, 255, 0.03); }

    .match-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .match-tc {
        font-family: var(--font-display);
        font-size: 0.9rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: 0.1em;
    }

    .match-meta {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }

    .meta-badge {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        letter-spacing: 0.08em;
        padding: 2px 6px;
        background: var(--surface-2);
        border: 1px solid var(--border);
        color: var(--text-muted);
    }
    .meta-badge.rated { border-color: var(--amber); color: var(--amber); background: rgba(255,171,0,0.08); }
    .meta-badge.private-badge { border-color: var(--red); color: var(--red); }

    .match-id {
        font-family: var(--font-mono);
        font-size: 0.5rem;
        color: var(--text-muted);
        opacity: 0.4;
        letter-spacing: 0.05em;
    }

    .join-btn {
        font-family: var(--font-display);
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        background: transparent;
        border: 1px solid var(--cyan);
        color: var(--cyan);
        padding: 8px 20px;
        cursor: pointer;
        transition: all 0.15s;
        flex-shrink: 0;
    }
    .join-btn:hover { background: var(--cyan-dim); box-shadow: var(--cyan-glow); }
    .join-btn:disabled { opacity: 0.4; cursor: not-allowed; }

    /* Stats bar */
    .stats-bar {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 12px 16px;
        background: var(--surface);
        border: 1px solid var(--border);
        flex-wrap: wrap;
    }

    .stat-block {
        display: flex;
        align-items: baseline;
        gap: 6px;
    }

    .stat-val {
        font-family: var(--font-display);
        font-size: 1rem;
        font-weight: 700;
        color: var(--cyan);
    }

    .stat-lbl {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--text-muted);
        letter-spacing: 0.1em;
    }

    .stat-sep {
        color: var(--border);
        font-family: var(--font-mono);
    }
</style>