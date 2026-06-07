// - ch355-client/src/lib/stores.ts -
import { writable, derived } from 'svelte/store';

export interface User {
    id: string;
    name: string;
    email: string;
    elo_rating: number;
    matches_played: number;
    matches_won: number;
    matches_lost: number;
    matches_drawn: number;
    conduct_score: number;
    resign_rate: number;
}

export interface Match {
    id: string;
    white_player_id: string | null;
    black_player_id: string | null;
    status: 'pending' | 'starting' | 'active' | 'completed' | 'canceled';
    is_rated: boolean;
    is_private: boolean;
    time_control: string;
    pgn_moves?: string;
    winner_id?: string | null;
    white_rating_change?: number | null;
    black_rating_change?: number | null;
    white_time_left?: number | null;
    black_time_left?: number | null;
}

// Auth
export const access_token = writable<string | null>(
    typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') : null
);
export const refresh_token = writable<string | null>(
    typeof localStorage !== 'undefined' ? localStorage.getItem('refresh_token') : null
);
export const current_user = writable<User | null>(null);

// Active game
export const active_match = writable<Match | null>(null);
export const current_fen = writable<string>('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
export const my_color = writable<'white' | 'black' | null>(null);
export const ws_connected = writable<boolean>(false);
export const game_over_info = writable<{
    reason: string;
    winner_id?: string;
    white_rating_change?: number;
    black_rating_change?: number;
} | null>(null);

// Lobby
export const open_matches = writable<Match[]>([]);

// Persist tokens to localStorage
if (typeof localStorage !== 'undefined') {
    access_token.subscribe(val => {
        if (val) localStorage.setItem('access_token', val);
        else localStorage.removeItem('access_token');
    });
    refresh_token.subscribe(val => {
        if (val) localStorage.setItem('refresh_token', val);
        else localStorage.removeItem('refresh_token');
    });
}

export const is_authenticated = derived(access_token, $t => !!$t);
