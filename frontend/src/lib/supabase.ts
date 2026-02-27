import {
  createClient,
  type SupabaseClient,
  type SupportedStorage,
} from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
export const supabaseConfigError =
  !SUPABASE_URL || !SUPABASE_ANON_KEY
    ? "Missing Supabase env vars: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY"
    : null;

// In-memory storage prevents token persistence in localStorage/sessionStorage.
class MemoryStorage implements SupportedStorage {
  private store = new Map<string, string>();

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }
}

const memoryStorage = new MemoryStorage();

export const supabase: SupabaseClient | null = supabaseConfigError
  ? null
  : createClient(SUPABASE_URL!, SUPABASE_ANON_KEY!, {
      auth: {
        persistSession: false,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        storage: memoryStorage,
      },
    });
