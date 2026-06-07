// - ch355-client/src/lib/api.ts -
import { get } from 'svelte/store';
import { access_token, refresh_token } from './stores';

export const BASE = 'http://127.0.0.1:8000/api';

export async function api<T = unknown>(
    path: string,
    options: RequestInit = {}
): Promise<{ data: T; message: string }> {
    const token = get(access_token);
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> || {})
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${BASE}${path}`, { ...options, headers });
    const json = await res.json();

    if (!res.ok) {
        throw new Error(json.detail || json.message || `HTTP ${res.status}`);
    }
    return json;
}

// WS URL: backend route is /api/game/ws/{match_id}
export function ws_url(match_id: string): string {
    const token = get(access_token);
    return `ws://127.0.0.1:8000/api/game/ws/${match_id}?token=${token}`;
}
