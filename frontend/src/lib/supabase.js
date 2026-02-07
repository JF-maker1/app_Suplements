import { createClient } from '@supabase/supabase-js';

// VITE_ environment variables jsou standard ve Vite projektech.
// Pokud nejsou nastaveny, aplikace upozorní v konzoli, ale nespadne okamžitě.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'YOUR_SUPABASE_URL';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'YOUR_SUPABASE_ANON_KEY';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);