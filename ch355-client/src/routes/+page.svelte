<!-- src/routes/+page.svelte -->
<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { access_token, current_user, is_authenticated } from '$lib/stores';
    import { api } from '$lib/api';

    let error_msg = $state('');
    let loading = $state(false);

    // If already authenticated, redirect
    onMount(() => {
        if ($is_authenticated) goto('/lobby');
    });

    // Google OAuth callback — expects google_credential from GSI
    async function handle_google_response(event: CustomEvent<{ credential: string }>) {
        loading = true;
        error_msg = '';
        try {
            const res = await api<{ access_token: string; refresh_token: string; user: typeof $current_user }>(
                '/auth/google',
                {
                    method: 'POST',
                    body: JSON.stringify({ id_token: event.detail.credential })
                }
            );
            const d = res.data as any;
            access_token.set(d.access_token);
            current_user.set(d.user);
            goto('/lobby');
        } catch (e: any) {
            error_msg = e.message || 'Authentication failed.';
        } finally {
            loading = false;
        }
    }

    // Inject Google GSI script and initialize
    onMount(() => {
        const script = document.createElement('script');
        script.src = 'https://accounts.google.com/gsi/client';
        script.async = true;
        script.defer = true;
        script.onload = () => {
            (window as any).google?.accounts.id.initialize({
                // Replace with your actual Google Client ID
                client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID || 'YOUR_GOOGLE_CLIENT_ID',
                callback: async (response: { credential: string }) => {
                    loading = true;
                    error_msg = '';
                    try {
                        const res = await api<any>('/auth/google', {
                            method: 'POST',
                            body: JSON.stringify({ id_token: response.credential })
                        });
                        const d = res.data;
                        access_token.set(d.access_token);
                        const me = await api<any>('/auth/me');
                        current_user.set(me.data);
                        goto('/lobby');
                    } catch (e: any) {
                        error_msg = e.message || 'Authentication failed.';
                    } finally {
                        loading = false;
                    }
                }
            });
            (window as any).google?.accounts.id.renderButton(
                document.getElementById('google-btn-container'),
                {
                    theme: 'outline',
                    size: 'large',
                    type: 'standard',
                    shape: 'rectangular',
                    text: 'signin_with',
                    width: 280
                }
            );
        };
        document.head.appendChild(script);
    });
</script>

<div class="login-page">
    <!-- Decorative corner brackets -->
    <div class="corner tl"></div>
    <div class="corner tr"></div>
    <div class="corner bl"></div>
    <div class="corner br"></div>

    <div class="login-card">
        <div class="card-header">
            <div class="header-line"></div>
            <span class="header-label">SYS::AUTH_MODULE</span>
            <div class="header-line"></div>
        </div>

        <div class="logo-block">
            <h1 class="title-big">CH<span class="accent">355</span></h1>
            <p class="subtitle">DISTRIBUTED CHESS INFRASTRUCTURE</p>
        </div>

        <div class="stat-row">
            <div class="stat">
                <span class="stat-val">v1.0.0</span>
                <span class="stat-lbl">RELEASE</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat">
                <span class="stat-val">ELO</span>
                <span class="stat-lbl">RATED</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat">
                <span class="stat-val">WS</span>
                <span class="stat-lbl">REALTIME</span>
            </div>
        </div>

        <div class="auth-section">
            <p class="auth-prompt">[ AUTHENTICATE TO PROCEED ]</p>
            <div id="google-btn-container" class="google-btn-wrap"></div>
            {#if loading}
                <p class="status-line">ESTABLISHING LINK...</p>
            {/if}
            {#if error_msg}
                <p class="error-line">ERR // {error_msg}</p>
            {/if}
        </div>

        <div class="card-footer">
            <span class="footer-text">NODES: REALTIME · POSTGRES · REDIS · FASTAPI</span>
        </div>
    </div>

    <!-- Decorative side glyphs -->
    <div class="side-glyph left">01001000 01001111 01010011 01010100</div>
    <div class="side-glyph right">01010111 01001000 01001001 01010100 01000101</div>
</div>

<style>
    .login-page {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        overflow: hidden;
    }

    /* Cyberpunk corner brackets */
    .corner {
        position: fixed;
        width: 40px;
        height: 40px;
        z-index: 10;
    }
    .corner.tl { top: 16px; left: 16px; border-top: 2px solid var(--cyan); border-left: 2px solid var(--cyan); }
    .corner.tr { top: 16px; right: 16px; border-top: 2px solid var(--cyan); border-right: 2px solid var(--cyan); }
    .corner.bl { bottom: 16px; left: 16px; border-bottom: 2px solid var(--cyan); border-left: 2px solid var(--cyan); }
    .corner.br { bottom: 16px; right: 16px; border-bottom: 2px solid var(--cyan); border-right: 2px solid var(--cyan); }

    .login-card {
        width: 420px;
        background: var(--surface);
        border: 1px solid var(--border);
        padding: 0;
        position: relative;
        box-shadow: 0 0 60px rgba(0, 229, 255, 0.08), inset 0 0 40px rgba(0, 229, 255, 0.03);
    }

    .card-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 12px 20px;
        border-bottom: 1px solid var(--border);
        background: rgba(0, 229, 255, 0.04);
    }

    .header-line {
        flex: 1;
        height: 1px;
        background: var(--border);
    }

    .header-label {
        font-family: var(--font-mono);
        font-size: 0.65rem;
        color: var(--text-muted);
        letter-spacing: 0.15em;
        white-space: nowrap;
    }

    .logo-block {
        padding: 2.5rem 2rem 1.5rem;
        text-align: center;
    }

    .title-big {
        font-family: var(--font-display);
        font-size: 4rem;
        font-weight: 900;
        color: var(--text-primary);
        letter-spacing: 0.08em;
        line-height: 1;
        text-shadow: 0 0 40px rgba(0, 229, 255, 0.2);
    }

    .accent {
        color: var(--cyan);
        text-shadow: var(--cyan-glow);
    }

    .subtitle {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        color: var(--text-muted);
        letter-spacing: 0.25em;
        margin-top: 0.5rem;
    }

    .stat-row {
        display: flex;
        align-items: stretch;
        border-top: 1px solid var(--border);
        border-bottom: 1px solid var(--border);
    }

    .stat {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 10px;
        gap: 2px;
    }

    .stat-val {
        font-family: var(--font-display);
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--cyan);
        letter-spacing: 0.1em;
    }

    .stat-lbl {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--text-muted);
        letter-spacing: 0.1em;
    }

    .stat-divider {
        width: 1px;
        background: var(--border);
    }

    .auth-section {
        padding: 2rem;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1.25rem;
    }

    .auth-prompt {
        font-family: var(--font-mono);
        font-size: 0.7rem;
        color: var(--text-muted);
        letter-spacing: 0.15em;
    }

    .google-btn-wrap {
        display: flex;
        justify-content: center;
        /* GSI injects an iframe - we just give it a home */
        min-height: 44px;
    }

    /* Override Google button to blend with dark theme */
    :global(#google-btn-container iframe) {
        filter: invert(0.1) hue-rotate(180deg) brightness(0.9);
    }

    .status-line {
        font-family: var(--font-mono);
        font-size: 0.65rem;
        color: var(--cyan);
        letter-spacing: 0.15em;
        animation: pulse 1s ease-in-out infinite;
    }

    @keyframes pulse { 50% { opacity: 0.4; } }

    .error-line {
        font-family: var(--font-mono);
        font-size: 0.65rem;
        color: var(--red);
        letter-spacing: 0.1em;
    }

    .card-footer {
        padding: 10px 20px;
        border-top: 1px solid var(--border);
        background: rgba(0, 0, 0, 0.3);
        text-align: center;
    }

    .footer-text {
        font-family: var(--font-mono);
        font-size: 0.55rem;
        color: var(--text-muted);
        letter-spacing: 0.1em;
    }

    .side-glyph {
        position: fixed;
        font-family: var(--font-mono);
        font-size: 0.6rem;
        color: rgba(0, 229, 255, 0.06);
        letter-spacing: 0.2em;
        writing-mode: vertical-rl;
        top: 50%;
        transform: translateY(-50%);
        user-select: none;
        pointer-events: none;
    }

    .side-glyph.left { left: 24px; }
    .side-glyph.right { right: 24px; transform: translateY(-50%) rotate(180deg); }
</style>
