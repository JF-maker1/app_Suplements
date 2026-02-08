import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Upload, FileText, CheckCircle, AlertCircle, Loader2, Pill, Activity, 
  ChevronRight, Ban, Search, Filter, Edit2, Save, X, ExternalLink, Tag, RefreshCw, Trash2,
  LayoutDashboard, FlaskConical, MessageSquare, Send, Bot, User, Sparkles, Database, Layers, Code, Play
} from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
// FIX: Použití ESM importu pro Supabase (řeší chybu "Could not resolve" v preview)
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// --- UTILS ---
function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// --- DYNAMIC API CONFIGURATION ---
const PROTOCOL = window.location.protocol;
const HOSTNAME = window.location.hostname;
const API_URL = `${PROTOCOL}//${HOSTNAME}:8000`;

// --- SUPABASE CLIENT ---
// FIX: Bezpečné načtení proměnných prostředí (řeší chybu "import.meta is not available")
const getEnv = () => {
  try {
    return import.meta.env || {};
  } catch {
    return {};
  }
};
const env = getEnv();
const supabaseUrl = env.VITE_SUPABASE_URL || 'YOUR_SUPABASE_URL';
const supabaseAnonKey = env.VITE_SUPABASE_ANON_KEY || 'YOUR_SUPABASE_ANON_KEY';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

// --- HOOKS ---
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => { clearTimeout(handler); };
  }, [value, delay]);
  return debouncedValue;
}

// =====================================================================
// COMPONENT: REPORT RENDERER (Inline)
// =====================================================================
const ReportRenderer = ({ reportId, params = {} }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        let query;
        if (reportId === 'report_magnesium_overview') {
          query = supabase
            .from('view_products_standardized')
            .select('*')
            .or('product_name.ilike.%magnesium%,ingredient_name.ilike.%magnesium%')
            .order('amount_mg', { ascending: false });
        } 
        else if (reportId === 'report_protein_overview') {
          query = supabase
            .from('view_products_standardized')
            .select('*')
            .ilike('product_name', '%protein%')
            .order('price', { ascending: true });
        }
        else {
           console.warn(`Report ID ${reportId} not implemented.`);
           setData([]); 
           setLoading(false);
           return;
        }

        const { data: result, error: dbError } = await query;
        if (dbError) throw dbError;
        setData(result || []);

      } catch (err) {
        console.error("Report Error:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (reportId) {
      fetchData();
    }
  }, [reportId]);

  if (loading) return <div className="p-4 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-600" /></div>;
  if (error) return <div className="p-4 text-red-600 bg-red-50 rounded">Chyba: {error}</div>;
  if (!data.length) return <div className="p-4 text-center text-slate-500">Žádná data.</div>;

  return (
    <div className="w-full overflow-hidden rounded-lg border border-slate-200 shadow-sm my-2 bg-white">
      <div className="bg-slate-50 px-3 py-2 border-b border-slate-200 font-bold text-xs uppercase text-slate-700">
        SQL REPORT: {reportId}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 border-b border-slate-100 text-xs text-slate-500 uppercase">
            <tr>
              <th className="px-3 py-2">Produkt</th>
              <th className="px-3 py-2 text-right">Množství</th>
              <th className="px-3 py-2 text-right">Cena</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((row, idx) => (
              <tr key={idx}>
                <td className="px-3 py-2">
                  <div className="font-medium text-slate-900 truncate max-w-[150px]">{row.product_name}</div>
                  <div className="text-[10px] text-slate-500 truncate">{row.ingredient_name}</div>
                </td>
                <td className="px-3 py-2 text-right font-mono">{row.amount_mg ? `${row.amount_mg} mg` : '-'}</td>
                <td className="px-3 py-2 text-right font-mono text-blue-600">{row.price ? `${row.price} ${row.currency || ''}` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// =====================================================================
// COMPONENT: CHAT WIDGET
// =====================================================================
const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ role: 'model', type: 'message', content: 'Ahoj! Jsem RDM Asistent. Zkus napsat "Srovnej hořčíky".' }]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isOpen]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMsg = { role: 'user', type: 'message', content: inputValue };
    setMessages(prev => [...prev, userMsg]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg.content, history: messages.map(m => ({ role: m.role, content: m.content || "" })) })
      });

      if (!response.ok) throw new Error("Chyba komunikace");
      const data = await response.json();
      
      setMessages(prev => [...prev, { role: 'model', type: data.type, content: data.content, payload: data.payload }]);

    } catch (error) {
      setMessages(prev => [...prev, { role: 'model', type: 'message', content: 'Omlouvám se, došlo k chybě.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return <button onClick={() => setIsOpen(true)} className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center z-50"><MessageSquare className="w-7 h-7" /></button>;

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[500px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50 overflow-hidden">
      <div className="bg-blue-600 p-4 flex justify-between items-center text-white">
        <div className="flex items-center gap-2"><Bot className="w-5 h-5" /><span className="font-bold text-sm">RDM Asistent</span></div>
        <button onClick={() => setIsOpen(false)}><X className="w-5 h-5" /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <div key={idx} className={clsx("flex gap-3", msg.role === 'user' ? "flex-row-reverse" : "flex-row")}>
            <div className={clsx("w-8 h-8 rounded-full flex items-center justify-center shrink-0", msg.role === 'user' ? "bg-slate-200" : "bg-blue-100 text-blue-600")}>{msg.role === 'user' ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}</div>
            <div className={clsx("max-w-[80%] rounded-2xl px-4 py-3 text-sm shadow-sm", msg.role === 'user' ? "bg-blue-600 text-white" : "bg-white border border-slate-100")}>
              {msg.type === 'command' ? <ReportRenderer reportId={msg.payload.report_id} params={msg.payload.params} /> : <p className="whitespace-pre-wrap">{msg.content}</p>}
            </div>
          </div>
        ))}
        {isLoading && <div className="text-xs text-slate-400 pl-12">Přemýšlím...</div>}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSendMessage} className="p-3 border-t bg-white flex gap-2"><input value={inputValue} onChange={e => setInputValue(e.target.value)} placeholder="Zeptej se..." className="flex-1 border rounded-xl px-4 py-2 text-sm" /><button type="submit" disabled={isLoading} className="p-2 bg-blue-600 text-white rounded-xl"><Send className="w-5 h-5" /></button></form>
    </div>
  );
};

// =====================================================================
// COMPONENT: DATA LAB
// =====================================================================
const DataLab = () => {
  const [query, setQuery] = useState("Kolik jsem utratil za proteiny?");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/lab/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }) });
      const data = await res.json();
      setResponse(data);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="bg-white p-4 rounded-xl border mb-6 shadow-sm">
        <form onSubmit={handleAnalyze} className="flex gap-4">
          <input value={query} onChange={e => setQuery(e.target.value)} className="flex-1 bg-slate-50 border rounded-lg px-4 py-3 text-sm font-mono" />
          <button type="submit" disabled={loading} className="px-6 bg-purple-600 text-white rounded-lg font-bold flex items-center gap-2">{loading ? <Loader2 className="animate-spin" /> : <Play />} Analyze</button>
        </form>
      </div>
      {response && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white p-4 rounded-xl border shadow-sm">
            <h3 className="font-bold text-slate-500 text-xs uppercase mb-2">Intent</h3>
            <div className="text-xl font-bold text-purple-600">{response.intent}</div>
          </div>
          <div className="bg-slate-900 p-4 rounded-xl shadow-sm text-green-400 font-mono text-xs overflow-auto max-h-96">
            <pre>{JSON.stringify(response, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
};

// =====================================================================
// MAIN APP COMPONENTS
// =====================================================================

const UploadZone = ({ onUploadSuccess }) => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const fileInputRef = useRef(null);

  const processFile = async (file) => {
    setIsAnalyzing(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API_URL}/scan/analyze`, { method: 'POST', body: formData });
      if (res.ok) onUploadSuccess();
    } catch (e) { console.error(e); } finally { setIsAnalyzing(false); }
  };

  return (
    <div onClick={() => fileInputRef.current.click()} className="h-32 border-2 border-dashed rounded-xl flex items-center justify-center cursor-pointer hover:bg-slate-50 transition-colors mb-6 bg-white">
      <input ref={fileInputRef} type="file" className="hidden" onChange={e => e.target.files[0] && processFile(e.target.files[0])} accept="image/*" />
      {isAnalyzing ? <div className="flex items-center gap-2 text-blue-600"><Loader2 className="animate-spin" /> Analyzuji...</div> : <div className="text-slate-500 flex items-center gap-2"><Upload /> Nahrát produkt</div>}
    </div>
  );
};

const ProductCard = ({ scan, onUpdate, onSourceClick }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const { data, image_url, source_url } = scan;
  
  useEffect(() => { 
    if (isEditing && data) { 
      setFormData({ 
        full_name: data.full_name || "", 
        brand: data.brand || "", 
        detected_price: data.detected_price || "", 
        currency: data.currency || "CZK", 
        source_url: source_url || "" 
      }); 
    } 
  }, [isEditing, data, source_url]);

  const handleSave = async () => {
    setIsSaving(true);
    
    // FIX: Flattened Payload for 422 Error Fix
    // Zploštění dat pro API (řeší chybu 422 Unprocessable Content)
    // Odesíláme plochý objekt { full_name, brand, ... } místo { data: { ... } }
    const updatePayload = { 
        full_name: formData.full_name,
        brand: formData.brand,
        detected_price: formData.detected_price ? Number(formData.detected_price) : null,
        currency: formData.currency,
        source_url: formData.source_url || null
    };

    const success = await onUpdate(scan.scan_id, updatePayload);
    setIsSaving(false);
    if (success) setIsEditing(false);
  };

  if (!data) return null;

  return (
    <div className="bg-white rounded-xl border shadow-sm hover:shadow-md transition-all overflow-hidden flex flex-col h-full">
      <div className="relative h-40 bg-slate-100">
        {image_url ? <img src={image_url} className="w-full h-full object-cover" /> : <div className="flex items-center justify-center h-full text-slate-400"><FileText /></div>}
        {!isEditing && <button onClick={() => setIsEditing(true)} className="absolute top-2 right-2 p-1.5 bg-white/90 rounded-lg hover:shadow-md"><Edit2 className="w-3.5 h-3.5 text-slate-600" /></button>}
      </div>
      <div className="p-4 flex-1 flex flex-col">
        {isEditing ? (
          <div className="space-y-3">
            <input value={formData.full_name} onChange={e => setFormData({...formData, full_name: e.target.value})} className="w-full text-sm p-1.5 border rounded" placeholder="Název" />
            <input value={formData.brand} onChange={e => setFormData({...formData, brand: e.target.value})} className="w-full text-sm p-1.5 border rounded" placeholder="Značka" />
            <div className="flex gap-2">
              <input type="number" value={formData.detected_price} onChange={e => setFormData({...formData, detected_price: e.target.value})} className="flex-1 text-sm p-1.5 border rounded" placeholder="Cena" />
              <select value={formData.currency} onChange={e => setFormData({...formData, currency: e.target.value})} className="w-20 text-sm p-1.5 border rounded"><option>CZK</option><option>EUR</option></select>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-2"><h3 className="font-bold text-slate-900 leading-tight line-clamp-2">{data.full_name}</h3><p className="text-xs text-blue-600 font-bold mt-1 uppercase">{data.brand}</p></div>
            <div className="mt-auto pt-3 border-t flex justify-between items-center">
              <div><span className="text-xs text-slate-400 block">Cena</span><span className="font-mono font-bold text-slate-700">{data.detected_price ? `${data.detected_price} ${data.currency}` : '—'}</span></div>
              {source_url && <button onClick={e => {e.stopPropagation(); onSourceClick(source_url)}} className="text-xs text-blue-500 flex items-center gap-1"><ExternalLink className="w-3 h-3" /> Zdroj</button>}
            </div>
          </>
        )}
      </div>
      {isEditing && (
        <div className="p-2 bg-slate-50 border-t flex gap-2">
          <button onClick={handleSave} disabled={isSaving} className="flex-1 bg-blue-600 text-white text-xs font-bold py-1.5 rounded flex justify-center items-center gap-1">{isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Uložit</button>
          <button onClick={() => setIsEditing(false)} className="px-3 bg-white border text-xs font-bold rounded">Zrušit</button>
        </div>
      )}
    </div>
  );
};

// --- APP ---
function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(Date.now());

  const fetchScans = useCallback(async () => {
    if (currentView !== 'dashboard') return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/scan/list?limit=50`);
      const data = await res.json();
      setScans(data);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, [currentView, lastUpdated]);

  useEffect(() => { fetchScans(); }, [fetchScans]);

  const updateScan = async (id, updateData) => {
    try {
      const res = await fetch(`${API_URL}/scan/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updateData) });
      if (!res.ok) throw new Error("Update failed");
      const updated = await res.json();
      setScans(prev => prev.map(s => s.scan_id === id ? updated : s));
      return true;
    } catch (e) { console.error(e); alert("Chyba ukládání."); return false; }
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      <header className="bg-white border-b h-16 flex items-center justify-between px-4 max-w-7xl mx-auto">
        <div className="font-bold text-xl cursor-pointer flex items-center gap-2" onClick={() => setCurrentView('dashboard')}><Activity className="text-blue-600" /> RDM Scanner</div>
        <div className="flex bg-slate-100 p-1 rounded-lg">
          <button onClick={() => setCurrentView('dashboard')} className={cn("px-3 py-1 text-xs font-bold rounded", currentView === 'dashboard' && "bg-white shadow text-blue-600")}>Dashboard</button>
          <button onClick={() => setCurrentView('lab')} className={cn("px-3 py-1 text-xs font-bold rounded", currentView === 'lab' && "bg-white shadow text-purple-600")}>Data Lab</button>
        </div>
      </header>
      <main className="min-h-[calc(100vh-64px)]">
        {currentView === 'lab' ? <DataLab /> : (
          <div className="max-w-7xl mx-auto px-4 py-8">
            <UploadZone onUploadSuccess={() => setLastUpdated(Date.now())} />
            {loading ? <div className="text-center py-20 text-slate-400"><Loader2 className="w-10 h-10 animate-spin mx-auto mb-4" />Načítám...</div> : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {scans.map(s => <ProductCard key={s.scan_id} scan={s} onUpdate={updateScan} onSourceClick={() => {}} />)}
              </div>
            )}
          </div>
        )}
      </main>
      <ChatWidget />
    </div>
  );
}

export default App;
