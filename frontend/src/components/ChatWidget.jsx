import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, X, Send, Bot, User, Sparkles, 
  ShoppingBag, TrendingUp, ChevronRight, ExternalLink,
  Loader2, AlertCircle, Database 
} from 'lucide-react';
import { clsx } from 'clsx';
import { createClient } from '@supabase/supabase-js';

// --- CONFIGURATION ---
const PROTOCOL = window.location.protocol;
const HOSTNAME = window.location.hostname;
const API_URL = `${PROTOCOL}//${HOSTNAME}:8000`;

// SUPABASE CLIENT (Inlined for Portability)
// Note: In production, this should be imported from ../lib/supabase.js
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

// --- SUB-COMPONENTS ---

/**
 * Komponenta pro zobrazení jedné karty produktu (Vector Result)
 */
const ProductCard = ({ item }) => {
  const name = item.full_name || "Neznámý produkt";
  const brand = item.brand || "Neznámá značka";
  const score = item.similarity ? Math.round(item.similarity * 100) : 0;
  const image = item.image_url || null; 

  return (
    <div className="min-w-[200px] w-[200px] bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col snap-start">
      <div className="h-24 bg-slate-100 relative flex items-center justify-center overflow-hidden">
        {image ? (
          <img src={image} alt={name} className="w-full h-full object-cover" />
        ) : (
          <ShoppingBag className="w-8 h-8 text-slate-300" />
        )}
        <div className="absolute top-1 right-1 bg-white/90 backdrop-blur px-1.5 py-0.5 rounded text-[10px] font-bold text-blue-600 border border-blue-100">
          {score}% shoda
        </div>
      </div>
      <div className="p-3 flex flex-col flex-1">
        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider truncate">
          {brand}
        </div>
        <div className="text-xs font-bold text-slate-900 leading-tight line-clamp-2 mb-2 h-8" title={name}>
          {name}
        </div>
        
        <div className="mt-auto pt-2 border-t border-slate-50 flex items-center justify-between">
           <span className="text-xs font-mono font-bold text-emerald-600">
             {item.extra_metadata?.detected_price 
               ? `${item.extra_metadata.detected_price} ${item.extra_metadata.currency || 'CZK'}` 
               : 'Cena?'}
           </span>
        </div>
      </div>
    </div>
  );
};

/**
 * Horizontální karusel pro seznam produktů
 */
const ProductCarousel = ({ items }) => {
  if (!items || items.length === 0) return null;

  return (
    <div className="mt-2 -mx-2">
      <div className="flex gap-3 overflow-x-auto px-2 pb-4 pt-1 snap-x scrollbar-hide">
        {items.map((item, idx) => (
          <ProductCard key={idx} item={item} />
        ))}
      </div>
    </div>
  );
};

/**
 * Jednoduchá tabulka pro SQL Data (Direct Payload)
 */
const DataTable = ({ data }) => {
  if (!data || !Array.isArray(data) || data.length === 0) return null;
  
  const headers = Object.keys(data[0]);

  return (
    <div className="mt-2 w-full overflow-hidden rounded-lg border border-slate-200 shadow-sm bg-white">
      <div className="bg-slate-50 px-3 py-1.5 border-b border-slate-200 flex items-center gap-2">
        <TrendingUp className="w-3 h-3 text-emerald-600" />
        <span className="text-[10px] font-bold text-slate-500 uppercase">Data Snapshot</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-100">
            <tr>
              {headers.map((h, i) => (
                <th key={i} className="px-2 py-1.5 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50">
                {headers.map((h, i) => (
                  <td key={i} className="px-2 py-1.5 whitespace-nowrap text-slate-700">
                    {typeof row[h] === 'object' ? JSON.stringify(row[h]) : String(row[h])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/**
 * INLINED: ReportRenderer (Legacy Support)
 * Handles direct SQL fetching for specific report IDs.
 */
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
          console.warn(`Report ID ${reportId} not implemented locally.`);
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

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-4 bg-slate-50 rounded-lg border border-slate-200">
        <Loader2 className="w-4 h-4 text-blue-600 animate-spin mb-1" />
        <span className="text-[10px] text-slate-500 font-mono">Fetching Data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-2 bg-red-50 text-red-700 rounded-lg text-xs border border-red-100">
        <AlertCircle className="w-3 h-3" />
        <span>Chyba: {error}</span>
      </div>
    );
  }

  if (!data || data.length === 0) return null;

  return (
    <div className="mt-2 w-full overflow-hidden rounded-lg border border-slate-200 shadow-sm bg-white">
      <div className="bg-slate-50 px-3 py-1.5 border-b border-slate-200 flex items-center justify-between">
        <span className="text-[10px] font-bold text-slate-700 uppercase flex items-center gap-1">
          <Database className="w-3 h-3 text-blue-500" />
          {reportId.replace('report_', '').replace('_', ' ')}
        </span>
      </div>
      <div className="overflow-x-auto max-h-[200px]">
        <table className="w-full text-xs text-left">
          <thead className="text-[10px] text-slate-500 uppercase bg-slate-50 border-b border-slate-100 sticky top-0">
            <tr>
              <th className="px-3 py-2 font-medium">Produkt</th>
              <th className="px-3 py-2 font-medium text-right">Množství</th>
              <th className="px-3 py-2 font-medium text-right">Cena</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50">
                <td className="px-3 py-1.5 truncate max-w-[120px]">{row.product_name}</td>
                <td className="px-3 py-1.5 text-right font-mono">{row.amount_mg ? `${row.amount_mg}` : '-'}</td>
                <td className="px-3 py-1.5 text-right font-mono text-blue-600">{row.price || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// --- MAIN COMPONENT ---

const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { 
      role: 'model', 
      type: 'text', 
      content: 'Ahoj! Jsem RDM Orchestrátor (v08.0). Zkus se zeptat: "Něco na spaní" (Vector) nebo "Nejlevnější protein" (SQL).' 
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isOpen]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    // 1. User Message
    const userMsg = { role: 'user', type: 'text', content: inputValue };
    setMessages(prev => [...prev, userMsg]);
    setInputValue("");
    setIsLoading(true);

    try {
      // 2. API Call (Orchestrator)
      const response = await fetch(`${API_URL}/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: userMsg.content,
          history: messages.map(m => ({ role: m.role, content: m.content || "" })) 
        })
      });

      if (!response.ok) throw new Error("API Error");

      const result = await response.json();
      
      // 3. Model Response
      setMessages(prev => [...prev, {
        role: 'model',
        type: result.type || 'text',
        content: result.content,
        payload: result.payload
      }]);

    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { role: 'model', type: 'text', content: 'Omlouvám se, server neodpovídá.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-purple-600 hover:bg-purple-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 z-50"
      >
        <MessageSquare className="w-7 h-7" />
        <span className="absolute -top-1 -right-1 flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
        </span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[600px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50 animate-in slide-in-from-bottom-5 duration-300 overflow-hidden font-sans">
      
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-blue-600 p-4 flex items-center justify-between text-white shadow-md">
        <div className="flex items-center gap-2">
          <div className="bg-white/20 p-1.5 rounded-lg backdrop-blur-sm">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-bold text-sm tracking-wide">RDM Orchestrator</h3>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse shadow-[0_0_5px_theme(colors.green.400)]"></span>
              <span className="text-[10px] opacity-90 font-medium">Neural Context Active</span>
            </div>
          </div>
        </div>
        <button onClick={() => setIsOpen(false)} className="hover:bg-white/20 p-1 rounded transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 bg-slate-50/50">
        {messages.map((msg, idx) => (
          <div key={idx} className={clsx("flex gap-3", msg.role === 'user' ? "flex-row-reverse" : "flex-row")}>
            
            {/* Avatar */}
            <div className={clsx(
              "w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm border",
              msg.role === 'user' 
                ? "bg-white border-slate-200 text-slate-600" 
                : "bg-purple-100 border-purple-200 text-purple-600"
            )}>
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
            </div>

            {/* Bubble Content */}
            <div className={clsx(
              "max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm",
              msg.role === 'user' 
                ? "bg-slate-800 text-white rounded-tr-none" 
                : "bg-white text-slate-700 border border-slate-200 rounded-tl-none"
            )}>
              
              {msg.content && (
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              )}

              {msg.type === 'product_cards' && msg.payload && (
                <ProductCarousel items={msg.payload} />
              )}

              {msg.type === 'data_table' && msg.payload && (
                <DataTable data={msg.payload} />
              )}

              {msg.type === 'command' && msg.payload?.command === 'EXECUTE_REPORT' && (
                <ReportRenderer reportId={msg.payload.report_id} params={msg.payload.params} />
              )}

            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3">
             <div className="w-8 h-8 bg-purple-50 border border-purple-100 rounded-full flex items-center justify-center shrink-0">
               <Sparkles className="w-4 h-4 text-purple-400 animate-pulse" />
             </div>
             <div className="bg-white border border-slate-100 rounded-2xl rounded-tl-none px-4 py-3 flex items-center gap-1 shadow-sm">
               <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
               <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
               <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></span>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSendMessage} className="p-3 bg-white border-t border-slate-200 flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Zeptej se (např. 'Co na energii?')..."
          className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:bg-white transition-all shadow-inner"
        />
        <button 
          type="submit" 
          disabled={!inputValue.trim() || isLoading}
          className="p-2.5 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
        >
          <Send className="w-5 h-5" />
        </button>
      </form>
    </div>
  );
};

export default ChatWidget;