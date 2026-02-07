import React, { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { Loader2, AlertCircle, Database } from 'lucide-react';

/**
 * Komponenta pro vizualizaci datových reportů (Agent Tools).
 * Načítá data přímo z SQL Views na základě ID reportu.
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

        // --- ROUTING REPORTŮ ---
        if (reportId === 'report_magnesium_overview') {
          // Zobrazit produkty, které mají v názvu Magnesium (nebo podle ingredience)
          // Používáme view_products_standardized definované v SQL migraci
          query = supabase
            .from('view_products_standardized')
            .select('*')
            // Hledáme buď v názvu produktu, nebo v názvu ingredience
            .or('product_name.ilike.%magnesium%,ingredient_name.ilike.%magnesium%')
            .order('amount_mg', { ascending: false }); // Seřadit podle síly
        } 
        else if (reportId === 'report_protein_overview') {
          query = supabase
            .from('view_products_standardized')
            .select('*')
            .ilike('product_name', '%protein%')
            .order('price', { ascending: true });
        }
        else {
          throw new Error(`Neznámý report ID: ${reportId}`);
        }

        // Exekuce
        const { data: result, error: dbError } = await query;
        
        if (dbError) throw dbError;
        setData(result);

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
      <div className="flex flex-col items-center justify-center p-8 bg-slate-50 rounded-lg border border-slate-200">
        <Loader2 className="w-6 h-6 text-blue-600 animate-spin mb-2" />
        <span className="text-xs text-slate-500 font-mono">Loading Real-Time Data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-4 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100">
        <AlertCircle className="w-4 h-4" />
        <span>Chyba při načítání dat: {error}</span>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="p-4 bg-slate-50 text-slate-500 rounded-lg text-sm text-center italic">
        Pro tento dotaz nebyla nalezena žádná data.
      </div>
    );
  }

  // --- VYKRESLENÍ TABULKY ---
  return (
    <div className="w-full overflow-hidden rounded-lg border border-slate-200 shadow-sm my-2 bg-white">
      <div className="bg-slate-50 px-3 py-2 border-b border-slate-200 flex items-center justify-between">
        <span className="text-xs font-bold text-slate-700 uppercase flex items-center gap-1">
          <Database className="w-3 h-3 text-blue-500" />
          SQL REPORT: {reportId.replace('report_', '').replace('_', ' ')}
        </span>
        <span className="text-[10px] text-slate-400 font-mono">{data.length} záznamů</span>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-100">
            <tr>
              <th className="px-3 py-2 font-medium">Produkt</th>
              <th className="px-3 py-2 font-medium text-right">Množství</th>
              <th className="px-3 py-2 font-medium text-right">Cena</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50 transition-colors">
                <td className="px-3 py-2">
                  <div className="font-medium text-slate-900 truncate max-w-[150px]" title={row.product_name}>
                    {row.product_name}
                  </div>
                  <div className="text-[10px] text-slate-500 truncate">{row.ingredient_name}</div>
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-700">
                  {row.amount_mg ? `${row.amount_mg} mg` : '—'}
                </td>
                <td className="px-3 py-2 text-right font-mono text-blue-600">
                  {row.price ? `${row.price} ${row.currency || ''}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ReportRenderer;