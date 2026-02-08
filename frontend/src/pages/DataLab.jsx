import React, { useState } from 'react';
import { 
  Play, Terminal, Database, Sparkles, Code, 
  AlertCircle, Loader2, ArrowRight, Layers 
} from 'lucide-react';
import { clsx } from 'clsx';

// Dynamic API URL (Inherited logic)
const PROTOCOL = window.location.protocol;
const HOSTNAME = window.location.hostname;
const API_URL = `${PROTOCOL}//${HOSTNAME}:8000`;

const DataLab = () => {
  const [query, setQuery] = useState("Kolik jsem utratil za proteiny?");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch(`${API_URL}/lab/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Server Error");
      }

      const data = await res.json();
      setResponse(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // --- HELPER: Intent Badge Color ---
  const getIntentColor = (intent) => {
    switch (intent) {
      case 'SQL_ANALYSIS': return 'bg-emerald-100 text-emerald-700 border-emerald-200';
      case 'VECTOR_SEARCH': return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'GENERAL_CHAT': return 'bg-slate-100 text-slate-700 border-slate-200';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 animate-in fade-in duration-300">
      
      {/* HEADER */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Layers className="w-6 h-6 text-purple-600" />
          Data Lab <span className="text-sm font-mono font-normal text-slate-400">| Developer Playground</span>
        </h2>
        <p className="text-slate-500 mt-1">Testování kaskády záměrů (Intent Router) a exekuce dotazů.</p>
      </div>

      {/* 1. INPUT ZONE */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-6">
        <form onSubmit={handleAnalyze} className="flex gap-4">
          <div className="flex-1 relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Zadejte analytický dotaz..."
              className="w-full pl-4 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:bg-white transition-all font-mono"
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            className="px-6 bg-purple-600 text-white font-bold rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
            Analyze
          </button>
        </form>
        {error && (
          <div className="mt-3 p-3 bg-red-50 text-red-700 text-sm rounded-lg flex items-center gap-2 border border-red-100">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}
      </div>

      {/* 2. RESULTS GRID (The Easel) */}
      {response && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* PANEL A: INTENT CLASSIFIER */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
            <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-500" />
              <span className="text-xs font-bold uppercase text-slate-500">Intent Classifier</span>
            </div>
            <div className="p-8 flex items-center justify-center flex-1 bg-slate-50/50">
              <div className={clsx("px-6 py-3 rounded-full border-2 text-xl font-bold tracking-wider shadow-sm", getIntentColor(response.intent))}>
                {response.intent}
              </div>
            </div>
          </div>

          {/* PANEL B: SQL AGENT */}
          <div className={clsx("bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col", 
              response.intent === 'SQL_ANALYSIS' ? 'border-emerald-200 ring-2 ring-emerald-100' : 'border-slate-200 opacity-60')}>
            <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-bold uppercase text-slate-500">SQL Agent</span>
            </div>
            <div className="p-4 flex-1 overflow-auto max-h-[300px]">
              {response.generated_sql ? (
                <>
                  <div className="bg-slate-900 text-slate-200 p-3 rounded-lg font-mono text-xs mb-4 overflow-x-auto">
                    {response.generated_sql}
                  </div>
                  {Array.isArray(response.results) && response.results.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left">
                        <thead className="bg-slate-100 text-slate-500 uppercase">
                          <tr>
                            {Object.keys(response.results[0]).slice(0, 4).map(k => (
                              <th key={k} className="px-2 py-1">{k}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {response.results.map((row, idx) => (
                            <tr key={idx} className="border-b border-slate-100">
                              {Object.values(row).slice(0, 4).map((val, vIdx) => (
                                <td key={vIdx} className="px-2 py-1 font-mono">{String(val)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="mt-2 text-[10px] text-slate-400 text-right">
                        Showing first 4 columns
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-400 italic text-sm text-center">No data returned or format invalid.</div>
                  )}
                </>
              ) : (
                <div className="text-slate-300 italic text-center mt-10">SQL Agent was not triggered.</div>
              )}
            </div>
          </div>

          {/* PANEL C: VECTOR AGENT */}
          <div className={clsx("bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col", 
              response.intent === 'VECTOR_SEARCH' ? 'border-blue-200 ring-2 ring-blue-100' : 'border-slate-200 opacity-60')}>
            <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-bold uppercase text-slate-500">Vector Agent (Mock)</span>
            </div>
            <div className="p-4 flex-1">
              {response.intent === 'VECTOR_SEARCH' ? (
                 <div className="space-y-2">
                   <div className="p-3 bg-blue-50 text-blue-800 rounded text-sm border border-blue-100">
                     {response.results?.message}
                   </div>
                   {response.results?.mock_matches?.map((match, idx) => (
                     <div key={idx} className="flex justify-between items-center p-2 bg-slate-50 rounded border border-slate-100 text-sm">
                        <span>{match.product}</span>
                        <span className="font-mono text-xs bg-slate-200 px-1 rounded">{match.similarity}</span>
                     </div>
                   ))}
                 </div>
              ) : (
                <div className="text-slate-300 italic text-center mt-10">Vector Agent was not triggered.</div>
              )}
            </div>
          </div>

          {/* PANEL D: RAW JSON */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
            <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center gap-2">
              <Code className="w-4 h-4 text-slate-500" />
              <span className="text-xs font-bold uppercase text-slate-500">Raw API Response</span>
            </div>
            <div className="p-0 flex-1 bg-slate-900 overflow-hidden relative">
              <pre className="text-[10px] text-green-400 font-mono p-4 overflow-auto max-h-[300px]">
                {JSON.stringify(response, null, 2)}
              </pre>
            </div>
          </div>

        </div>
      )}
    </div>
  );
};

export default DataLab;