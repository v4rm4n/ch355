// - ch355-client/src/lib/chess_utils.ts -

// Format seconds as M:SS
export function format_clock(seconds: number | null): string {
    if (seconds === null || seconds === undefined) return '∞';
    const total = Math.max(0, Math.floor(seconds));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// Parse time control string like "10+0" → base seconds
export function parse_time_control(tc: string): { base: number; increment: number } {
    if (tc.toLowerCase() === 'untimed') return { base: 0, increment: 0 };
    const [b, i] = tc.split('+').map(Number);
    return { base: (b || 10) * 60, increment: i || 0 };
}

export function time_control_label(tc: string): string {
    if (tc.toLowerCase() === 'untimed') return 'Untimed';
    const { base } = parse_time_control(tc);
    const mins = base / 60;
    if (mins <= 3) return `Bullet ${tc}`;
    if (mins <= 5) return `Blitz ${tc}`;
    if (mins <= 15) return `Rapid ${tc}`;
    return `Classical ${tc}`;
}

// Strip PGN clock comments so chess.js can parse cleanly
// Backend embeds { [%clk H:MM:SS.mmm] } in PGN comments
export function strip_pgn_comments(pgn: string): string {
    // Remove { ... } comment blocks
    return pgn.replace(/\{[^}]*\}/g, '').replace(/\s+/g, ' ').trim();
}
