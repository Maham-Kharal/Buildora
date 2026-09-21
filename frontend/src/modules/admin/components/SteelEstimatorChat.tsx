'use client';

import React, { useState } from 'react';
import { Calculator, Sparkles, Building, MapPin, Search, DollarSign, Award, CheckCircle2 } from 'lucide-react';
import { adminService } from '../services/adminService';
import { SteelEstimateResponse } from '@/core/types';

export const SteelEstimatorChat: React.FC = () => {
  const [projectName, setProjectName] = useState('Austin Commercial Tower B');
  const [projectType, setProjectType] = useState('Commercial');
  const [sqft, setSqft] = useState<number>(45000);
  const [rebarGrade, setRebarGrade] = useState('Grade 60');
  const [location, setLocation] = useState('Austin, Texas, US');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SteelEstimateResponse | null>(null);

  const handleEstimate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await adminService.estimateSteel({
        project_name: projectName,
        project_type: projectType,
        total_sqft: sqft,
        rebar_grade: rebarGrade,
        location: location,
      });
      setResult(res);
    } catch (err) {
      alert('Error calculating steel estimation.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Calculator Input Form */}
      <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-[#C28E64] p-3 rounded-2xl text-white shadow-md">
            <Calculator className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-stone-900">AI Grade 60 Steel Takeoff Estimator</h3>
            <p className="text-xs text-stone-500">
              US Spec estimation (~4.5 lbs/sqft) + Tavily market rate lookup + 25 historical project similarity search
            </p>
          </div>
        </div>

        <form onSubmit={handleEstimate} className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Project Name</label>
            <input
              type="text"
              required
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Project Type</label>
            <select
              value={projectType}
              onChange={(e) => setProjectType(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            >
              <option value="Commercial">Commercial Structural</option>
              <option value="Residential">Residential High-Rise</option>
              <option value="Bridge / Civil">Bridge Heavy Civil</option>
              <option value="Industrial">Industrial Warehouse</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Total Square Feet (sqft)</label>
            <input
              type="number"
              required
              min="100"
              value={sqft}
              onChange={(e) => setSqft(Number(e.target.value))}
              className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">Steel Rebar Spec</label>
            <input
              type="text"
              disabled
              value={rebarGrade}
              className="w-full px-3.5 py-2.5 border border-stone-200 bg-stone-100 rounded-xl text-sm font-semibold text-stone-700"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-700 mb-1">US Location</label>
            <input
              type="text"
              required
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:ring-2 focus:ring-[#C28E64]"
            />
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#C28E64] hover:bg-[#A8754F] text-white py-2.5 rounded-xl font-bold text-sm shadow transition flex items-center justify-center space-x-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>{loading ? 'Running AI Takeoff...' : 'Calculate Steel & Match Past Projects'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Results Section */}
      {result && (
        <div className="space-y-6 animate-fade-in">
          {/* Main Calculation Summary */}
          <div className="bg-gradient-to-br from-[#1E1E1E] to-stone-900 text-white rounded-2xl p-6 shadow-xl border border-stone-800 space-y-5">
            <div className="flex items-center justify-between border-b border-stone-800 pb-4">
              <div>
                <span className="text-xs text-[#C28E64] font-bold uppercase tracking-wider block">
                  AI Estimation Result ({result.currency})
                </span>
                <h4 className="text-xl font-extrabold">{result.project_name}</h4>
              </div>
              <div className="bg-[#C28E64]/20 border border-[#C28E64]/40 text-[#C28E64] text-xs font-bold px-3.5 py-1.5 rounded-full flex items-center space-x-1.5">
                <Search className="w-3.5 h-3.5" />
                <span>{result.market_source}</span>
              </div>
            </div>

            {/* Tavily Web Search Source & Citation Block */}
            {result.search_query_used && (
              <div className="bg-stone-800/80 p-3.5 rounded-xl border border-stone-700 text-xs space-y-1">
                <div className="flex items-center space-x-2 text-emerald-400 font-bold">
                  <Search className="w-4 h-4" />
                  <span>Tavily Live Web Search API Query Executed:</span>
                </div>
                <p className="font-mono text-stone-300 text-[11px] bg-stone-900/60 p-2 rounded-lg border border-stone-800">
                  "{result.search_query_used}"
                </p>
                <p className="text-stone-400 text-[11px]">
                  Scraped live market data: Grade 60 rebar price per US Ton in {location} verified at <strong>${result.live_market_price_per_ton.toFixed(2)} USD / Ton</strong>.
                </p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-stone-800/60 p-4 rounded-xl border border-stone-700">
                <span className="text-xs text-stone-400 block font-medium">Estimated Grade 60 Rebar</span>
                <span className="text-2xl font-black text-amber-400">{result.estimated_rebar_tons} US Tons</span>
              </div>

              <div className="bg-stone-800/60 p-4 rounded-xl border border-stone-700">
                <span className="text-xs text-stone-400 block font-medium">Live Market Rate / Ton</span>
                <span className="text-2xl font-black text-emerald-400">
                  ${result.live_market_price_per_ton.toFixed(2)}
                </span>
              </div>

              <div className="bg-stone-800/60 p-4 rounded-xl border border-stone-700">
                <span className="text-xs text-stone-400 block font-medium">Total Estimated Cost ($USD)</span>
                <span className="text-2xl font-black text-white">
                  ${result.total_estimated_cost_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>

            {/* Step-by-Step Formula & Obtaining Final Answer Banner */}
            {result.calculation_steps && (
              <div className="bg-stone-950 p-4 rounded-xl border border-[#C28E64]/40 space-y-2 text-xs">
                <span className="font-bold text-[#C28E64] block">🧮 Step-by-Step Takeoff Calculation:</span>
                <pre className="text-stone-300 font-mono text-[11px] whitespace-pre-line leading-relaxed">
                  {result.calculation_steps}
                </pre>
                <div className="pt-2 border-t border-stone-800 flex items-center space-x-2 text-emerald-400 font-extrabold text-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span>Obtaining Final Answer: ${result.total_estimated_cost_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })} USD</span>
                </div>
              </div>
            )}
          </div>

          {/* Historical Similarity Results (Top 3 of 25 projects) */}
          <div className="bg-white rounded-2xl p-6 shadow-md border border-stone-200">
            <h4 className="text-base font-bold text-stone-900 mb-2 flex items-center space-x-2">
              <Award className="w-5 h-5 text-[#C28E64]" />
              <span>Top Similar Past Projects (Matched from 25 Takeoff Dataset)</span>
            </h4>
            <p className="text-xs text-stone-500 mb-4">
              Cross-referenced against historical project database by floor area & structural density
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {result.similar_historical_projects.map((proj, idx) => (
                <div key={idx} className="bg-stone-50 p-4 rounded-2xl border border-stone-200 space-y-2 relative">
                  <div className="flex justify-between items-start">
                    <h5 className="font-bold text-stone-900 text-sm">{proj.name}</h5>
                    <span className="bg-emerald-100 text-emerald-800 font-bold text-[11px] px-2 py-0.5 rounded-full border border-emerald-200">
                      {proj.similarity_score}% Match
                    </span>
                  </div>
                  <div className="text-xs text-stone-500 space-y-1">
                    <p>Type: <span className="font-semibold text-stone-700">{proj.project_type}</span></p>
                    <p>Area: <span className="font-semibold text-stone-700">{proj.sqft.toLocaleString()} sqft</span></p>
                    <p>Steel Used: <span className="font-bold text-amber-800">{proj.steel_tons_used} Tons</span></p>
                    <p>Past Cost: <span className="font-mono font-bold text-stone-900">${proj.cost_usd.toLocaleString()} USD</span></p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
