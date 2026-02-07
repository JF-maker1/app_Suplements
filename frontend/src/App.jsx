import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Upload, FileText, CheckCircle, AlertCircle, Loader2, Pill, Activity, 
  ChevronRight, Ban, Search, Filter, Edit2, Save, X, ExternalLink, Tag, RefreshCw, Trash2
} from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// IMPORT CHAT WIDGET
import ChatWidget from './components/ChatWidget';

// --- UTILS ---
function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// --- DYNAMIC API CONFIGURATION ---
// Změna: Dynamické zjištění IP adresy serveru.
// Pokud běží frontend na localhost, použije localhost.
// Pokud běží na 192.168.x.x, použije tuto IP i pro backend (port 8000).
const PROTOCOL = window.location.protocol;
const HOSTNAME = window.location.hostname;
const API_URL = `${PROTOCOL}//${HOSTNAME}:8000`;

// --- HOOKS ---
// Custom hook pro debounce hodnoty (zpoždění vyhledávání)
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// --- COMPONENTS ---

// 1. Header
const Header = () => (
  <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-sm">
    <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className="bg-blue-600 p-2 rounded-lg shadow-lg shadow-blue-600/20">
          <Activity className="w-5 h-5 text-white" />
        </div>
        <h1 className="font-bold text-xl tracking-tight text-slate-900">
          RDM <span className="text-blue-600">ProductScanner</span>
        </h1>
      </div>
      <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
        <span className="hidden sm:inline">Cycle 5 | Agentic Mode | Dashboard</span>
        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
      </div>
    </div>
  </header>
);

// 2. Upload Zone (Compact Version)
const UploadZone = ({ onUploadSuccess }) => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const processFile = async (file) => {
    setIsAnalyzing(true);
    setError(null);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_URL}/scan/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error(`Upload Failed: ${response.status}`);
      
      const data = await response.json();
      if (data.status === 'PARSED') {
        onUploadSuccess(data); // Callback do rodiče
      } else {
        throw new Error("Analýza nevrátila validní data.");
      }
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Drag & Drop Handlers
  const handleDrag = (e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) processFile(e.dataTransfer.files[0]);
  };

  return (
    <div className="mb-6">
      <form
        className={cn(
          "relative h-32 flex flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all duration-200 cursor-pointer overflow-hidden group",
          dragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50",
          isAnalyzing && "pointer-events-none opacity-80 bg-slate-50"
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input ref={inputRef} type="file" className="hidden" onChange={(e) => e.target.files?.[0] && processFile(e.target.files[0])} accept="image/*" />

        {isAnalyzing ? (
          <div className="flex items-center gap-3">
            <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
            <span className="font-medium text-slate-700">Analyzuji obraz (Gemini AI)...</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-center">
            <div className="flex items-center gap-2 text-slate-600 group-hover:text-blue-600 transition-colors">
              <Upload className="w-5 h-5" />
              <span className="font-medium">Nahrát nový produkt</span>
            </div>
            <p className="text-xs text-slate-400">Podporuje JPG, PNG (Max 5MB)</p>
          </div>
        )}
      </form>
      {error && (
        <div className="mt-2 text-xs text-red-600 flex items-center gap-1">
          <Ban className="w-3 h-3" /> {error}
        </div>
      )}
    </div>
  );
};

// 3. Filter Bar
const FilterBar = ({ filters, setFilters, onReset }) => {
  return (
    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-6 flex flex-col md:flex-row gap-4 items-end md:items-center">
      
      {/* Search Query */}
      <div className="flex-1 w-full relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Hledat produkt..."
          value={filters.q}
          onChange={(e) => setFilters(prev => ({ ...prev, q: e.target.value }))}
          className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
        />
      </div>

      {/* Price Range */}
      <div className="flex items-center gap-2 w-full md:w-auto">
        <div className="flex items-center gap-2 bg-slate-50 px-3 py-2 rounded-lg border border-slate-200">
          <span className="text-xs text-slate-500 font-medium">Cena:</span>
          <input
            type="number"
            placeholder="Od"
            value={filters.minPrice}
            onChange={(e) => setFilters(prev => ({ ...prev, minPrice: e.target.value }))}
            className="w-16 bg-transparent text-sm focus:outline-none border-b border-transparent focus:border-blue-500 text-center"
          />
          <span className="text-slate-300">-</span>
          <input
            type="number"
            placeholder="Do"
            value={filters.maxPrice}
            onChange={(e) => setFilters(prev => ({ ...prev, maxPrice: e.target.value }))}
            className="w-16 bg-transparent text-sm focus:outline-none border-b border-transparent focus:border-blue-500 text-center"
          />
        </div>
      </div>

      {/* Active Filters / Reset */}
      {(filters.sourceUrl || filters.minPrice || filters.maxPrice) && (
        <div className="flex items-center gap-2">
           <button 
            onClick={onReset}
            className="p-2 hover:bg-red-50 text-slate-500 hover:text-red-600 rounded-lg transition-colors"
            title="Resetovat filtry"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}
      
      {filters.sourceUrl && (
         <div className="hidden md:flex items-center gap-1 bg-blue-50 text-blue-700 px-3 py-2 rounded-lg text-xs font-medium border border-blue-100 max-w-[200px]">
           <Tag className="w-3 h-3 shrink-0" />
           <span className="truncate">Zdroj: {new URL(filters.sourceUrl).hostname}</span>
         </div>
      )}

    </div>
  );
};

// 4. Product Card (Editable)
const ProductCard = ({ scan, onUpdate, onSourceClick }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  const { data, image_url, source_url } = scan;
  
  // Initialize formData when entering edit mode
  useEffect(() => {
    if (isEditing && data) {
      setFormData({
        full_name: data.full_name || "",
        brand: data.brand || "",
        detected_price: data.detected_price || "",
        currency: data.currency || "CZK",
        source_url: source_url || "",
      });
    }
  }, [isEditing, data, source_url]);

  const handleSave = async () => {
    setIsSaving(true);
    const updatePayload = {
      data: {
        full_name: formData.full_name,
        brand: formData.brand,
        detected_price: formData.detected_price ? Number(formData.detected_price) : null,
        currency: formData.currency,
      },
      source_url: formData.source_url || null,
    };

    const success = await onUpdate(scan.scan_id, updatePayload);
    setIsSaving(false);
    if (success) setIsEditing(false);
  };

  if (!data) return null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-300 overflow-hidden flex flex-col h-full">
      
      {/* Header Image */}
      <div className="relative h-40 bg-slate-100 overflow-hidden border-b border-slate-100">
        {image_url ? (
          <img src={image_url} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400">
            <FileText className="w-8 h-8" />
          </div>
        )}
        
        {/* Top-right Edit Button */}
        {!isEditing && (
          <button 
            onClick={() => setIsEditing(true)}
            className="absolute top-2 right-2 p-1.5 bg-white/90 backdrop-blur-sm rounded-lg shadow-sm hover:bg-white hover:shadow-md transition-all"
          >
            <Edit2 className="w-3.5 h-3.5 text-slate-600" />
          </button>
        )}
      </div>

      {/* Body */}
      <div className="p-4 flex-1 flex flex-col">
        {isEditing ? (
          // --- EDIT MODE ---
          <div className="space-y-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Název</label>
              <input 
                type="text" 
                value={formData.full_name || ""} 
                onChange={e => setFormData({...formData, full_name: e.target.value})}
                className="w-full text-sm p-1.5 border border-slate-300 rounded mt-1" 
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Značka</label>
              <input 
                type="text" 
                value={formData.brand || ""} 
                onChange={e => setFormData({...formData, brand: e.target.value})}
                className="w-full text-sm p-1.5 border border-slate-300 rounded mt-1" 
              />
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Cena</label>
                <input 
                  type="number" 
                  value={formData.detected_price || ""} 
                  onChange={e => setFormData({...formData, detected_price: e.target.value})}
                  className="w-full text-sm p-1.5 border border-slate-300 rounded mt-1" 
                />
              </div>
              <div className="w-20">
                <label className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Měna</label>
                <select 
                  value={formData.currency || "CZK"} 
                  onChange={e => setFormData({...formData, currency: e.target.value})}
                  className="w-full text-sm p-1.5 border border-slate-300 rounded mt-1"
                >
                  <option value="CZK">CZK</option>
                  <option value="EUR">EUR</option>
                  <option value="USD">USD</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">URL</label>
              <input 
                type="text" 
                value={formData.source_url || ""} 
                onChange={e => setFormData({...formData, source_url: e.target.value})}
                className="w-full text-xs p-1.5 border border-slate-300 rounded font-mono text-slate-600" 
                placeholder="https://..."
              />
            </div>
          </div>
        ) : (
          // --- VIEW MODE ---
          <>
            <div className="mb-2">
              <h3 className="font-bold text-slate-900 leading-tight line-clamp-2" title={data.full_name}>
                {data.full_name}
              </h3>
              <p className="text-xs text-blue-600 font-bold mt-1 uppercase tracking-wider">{data.brand}</p>
            </div>

            <div className="mt-auto pt-3 border-t border-slate-50 flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-xs text-slate-400">Cena</span>
                <span className="font-mono font-bold text-slate-700">
                  {data.detected_price ? `${data.detected_price} ${data.currency || 'CZK'}` : '—'}
                </span>
              </div>
              
              <div className="flex flex-col items-end max-w-[50%]">
                 <span className="text-xs text-slate-400">Zdroj</span>
                 {source_url ? (
                   <button 
                    onClick={(e) => { e.stopPropagation(); onSourceClick(source_url); }}
                    className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700 hover:underline truncate max-w-full"
                    title={source_url}
                   >
                     <ExternalLink className="w-3 h-3 shrink-0" />
                     <span className="truncate">{new URL(source_url).hostname}</span>
                   </button>
                 ) : (
                   <span className="text-xs text-slate-300 italic">Neuveden</span>
                 )}
              </div>
            </div>
            
            {/* Ingredients Preview */}
            <div className="mt-3 flex flex-wrap gap-1">
              {data.composition?.active_ingredients?.slice(0, 2).map((ing, idx) => (
                <span key={idx} className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                  {ing.name}
                </span>
              ))}
              {(data.composition?.active_ingredients?.length || 0) > 2 && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-50 text-slate-400">
                  +{data.composition.active_ingredients.length - 2} další
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {/* Edit Footer */}
      {isEditing && (
        <div className="p-2 bg-slate-50 border-t border-slate-200 flex gap-2">
          <button 
            onClick={handleSave} 
            disabled={isSaving}
            className="flex-1 bg-blue-600 text-white text-xs font-bold py-1.5 rounded hover:bg-blue-700 flex justify-center items-center gap-1"
          >
            {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Uložit
          </button>
          <button 
            onClick={() => setIsEditing(false)}
            className="px-3 bg-white border border-slate-300 text-slate-600 text-xs font-bold rounded hover:bg-slate-50"
          >
            Zrušit
          </button>
        </div>
      )}
    </div>
  );
};


// --- MAIN APP ---
function App() {
  // State
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    q: "",
    minPrice: "",
    maxPrice: "",
    sourceUrl: ""
  });
  const [lastUpdated, setLastUpdated] = useState(Date.now()); // Trigger for refetch

  // Debounced Search Query
  const debouncedQ = useDebounce(filters.q, 500);

  // FETCH SCANS
  const fetchScans = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (debouncedQ) params.append("q", debouncedQ);
      if (filters.sourceUrl) params.append("source_url", filters.sourceUrl);
      if (filters.minPrice) params.append("min_price", filters.minPrice);
      if (filters.maxPrice) params.append("max_price", filters.maxPrice);
      params.append("limit", "50"); // Hard limit for dashboard

      const res = await fetch(`${API_URL}/scan/list?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch");
      
      const data = await res.json();
      setScans(data);
    } catch (e) {
      console.error("Fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, filters.sourceUrl, filters.minPrice, filters.maxPrice, lastUpdated]);

  // Initial & Dependency Fetch
  useEffect(() => {
    fetchScans();
  }, [fetchScans]);

  // UPDATE SCAN (PATCH)
  const updateScan = async (id, updateData) => {
    try {
      const res = await fetch(`${API_URL}/scan/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updateData),
      });

      if (!res.ok) throw new Error("Update failed");
      
      const updatedRecord = await res.json();
      
      // Local Update (Optimistic-like but safe)
      setScans(prev => prev.map(s => s.scan_id === id ? updatedRecord : s));
      
      return true;
    } catch (e) {
      console.error("Update error:", e);
      alert("Chyba při ukládání změn.");
      return false;
    }
  };

  const handleSourceFilter = (url) => {
    setFilters(prev => ({ ...prev, sourceUrl: url }));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleResetFilters = () => {
    setFilters({ q: "", minPrice: "", maxPrice: "", sourceUrl: "" });
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-8">
        
        {/* TOP SECTION: Upload & Stats */}
        <div className="mb-8">
          <UploadZone onUploadSuccess={() => setLastUpdated(Date.now())} />
        </div>

        {/* MIDDLE SECTION: Filters */}
        <FilterBar 
          filters={filters} 
          setFilters={setFilters} 
          onReset={handleResetFilters} 
        />

        {/* BOTTOM SECTION: Grid */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Loader2 className="w-10 h-10 animate-spin mb-4 text-blue-500" />
            <p>Načítám produkty...</p>
          </div>
        ) : scans.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-in fade-in duration-500">
            {scans.map((scan) => (
              <ProductCard 
                key={scan.scan_id} 
                scan={scan} 
                onUpdate={updateScan} 
                onSourceClick={handleSourceFilter}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-20 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <div className="mx-auto w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-4">
              <Search className="w-8 h-8 text-slate-300" />
            </div>
            <h3 className="text-lg font-bold text-slate-700">Žádné produkty nenalezeny</h3>
            <p className="text-slate-500 max-w-sm mx-auto mt-2">
              Zkuste změnit filtry nebo nahrajte nový produkt.
            </p>
            {(filters.q || filters.sourceUrl) && (
              <button onClick={handleResetFilters} className="mt-4 text-blue-600 hover:underline text-sm font-medium">
                Zrušit všechny filtry
              </button>
            )}
          </div>
        )}

      </main>

      {/* --- AGENTIC WIDGET INTEGRATION --- */}
      <ChatWidget />
    </div>
  );
}

export default App;