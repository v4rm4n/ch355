<!-- src/routes/+layout.svelte -->
<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { access_token, current_user, is_authenticated } from '$lib/stores';
    import { api } from '$lib/api';

    let { children } = $props();

    onMount(async () => {
        if ($access_token) {
            try {
                const res = await api<typeof $current_user>('/auth/me');
                current_user.set(res.data);
            } catch {
                access_token.set(null);
                current_user.set(null);
            }
        }
    });

    function handle_logout() {
        access_token.set(null);
        current_user.set(null);
        goto('/');
    }

    const on_game_page = $derived($page.url.pathname.startsWith('/game'));
</script>

<svelte:head>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600&display=swap" rel="stylesheet">
</svelte:head>

<div class="app-shell">
    <!-- Scanline overlay -->
    <div class="scanlines" aria-hidden="true"></div>
    <!-- Grid background -->
    <div class="grid-bg" aria-hidden="true"></div>

    {#if !on_game_page}
    <header class="site-header">
        <a href={$is_authenticated ? '/lobby' : '/'} class="logo">
            <span class="logo-ch">CH</span><span class="logo-355">355</span>
            <span class="logo-blink">_</span>
        </a>

        <nav class="nav-links">
            {#if $is_authenticated}
                <a href="/lobby" class="nav-link">LOBBY</a>
                <div class="nav-user">
                    <span class="user-elo">{$current_user?.elo_rating ?? '—'}</span>
                    <span class="user-name">{$current_user?.name ?? '...'}</span>
                </div>
                <button class="nav-btn-logout" onclick={handle_logout}>DISCONNECT</button>
            {/if}
        </nav>
    </header>
    {/if}

    <main class="main-content" class:no-header={on_game_page}>
        {@render children()}
    </main>
</div>

<style>
    :global(*, *::before, *::after) {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }

    :global(body) {
        background: #020408;
        color: #c8d8e8;
        font-family: 'Rajdhani', 'Share Tech Mono', monospace;
        min-height: 100vh;
        overflow-x: hidden;
    }

    :global(:root) {
        --cyan: #00e5ff;
        --cyan-dim: rgba(0, 229, 255, 0.15);
        --cyan-glow: 0 0 20px rgba(0, 229, 255, 0.4);
        --red: #ff1744;
        --red-dim: rgba(255, 23, 68, 0.15);
        --green: #00e676;
        --amber: #ffab00;
        --bg: #020408;
        --surface: #080f1a;
        --surface-2: #0d1a2d;
        --border: rgba(0, 229, 255, 0.2);
        --border-bright: rgba(0, 229, 255, 0.5);
        --text-primary: #e0f0ff;
        --text-muted: #4a6a8a;
        --font-mono: 'Share Tech Mono', monospace;
        --font-display: 'Orbitron', sans-serif;
        --font-body: 'Rajdhani', sans-serif;
    }

    .app-shell {
        position: relative;
        min-height: 100vh;
    }

    .scanlines {
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 9999;
        background: repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0, 0, 0, 0.03) 2px,
            rgba(0, 0, 0, 0.03) 4px
        );
    }

    .grid-bg {
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 0;
        background-image:
            linear-gradient(rgba(0, 229, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 229, 255, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
    }

    .site-header {
        position: relative;
        z-index: 100;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 2rem;
        height: 56px;
        border-bottom: 1px solid var(--border);
        background: linear-gradient(180deg, rgba(0,229,255,0.04) 0%, transparent 100%);
    }

    .logo {
        text-decoration: none;
        font-family: var(--font-display);
        font-size: 1.4rem;
        font-weight: 900;
        letter-spacing: 0.1em;
        display: flex;
        align-items: baseline;
        gap: 0;
    }

    .logo-ch {
        color: var(--cyan);
        text-shadow: var(--cyan-glow);
    }

    .logo-355 {
        color: var(--text-primary);
    }

    .logo-blink {
        color: var(--cyan);
        animation: blink 1.2s step-end infinite;
        margin-left: 2px;
    }

    @keyframes blink { 50% { opacity: 0; } }

    .nav-links {
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }

    .nav-link {
        font-family: var(--font-mono);
        font-size: 0.75rem;
        letter-spacing: 0.15em;
        color: var(--text-muted);
        text-decoration: none;
        transition: color 0.2s, text-shadow 0.2s;
    }

    .nav-link:hover {
        color: var(--cyan);
        text-shadow: var(--cyan-glow);
    }

    .nav-user {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0;
    }

    .user-name {
        font-family: var(--font-mono);
        font-size: 0.7rem;
        color: var(--cyan);
        letter-spacing: 0.08em;
    }

    .user-elo {
        font-family: var(--font-display);
        font-size: 0.65rem;
        color: var(--amber);
        letter-spacing: 0.1em;
    }

    .nav-btn-logout {
        font-family: var(--font-mono);
        font-size: 0.65rem;
        letter-spacing: 0.12em;
        color: var(--red);
        background: transparent;
        border: 1px solid var(--red);
        padding: 4px 10px;
        cursor: pointer;
        transition: background 0.2s, box-shadow 0.2s;
    }

    .nav-btn-logout:hover {
        background: var(--red-dim);
        box-shadow: 0 0 12px rgba(255,23,68,0.3);
    }

    .main-content {
        position: relative;
        z-index: 1;
        min-height: calc(100vh - 56px);
    }

    .main-content.no-header {
        min-height: 100vh;
    }
</style>
