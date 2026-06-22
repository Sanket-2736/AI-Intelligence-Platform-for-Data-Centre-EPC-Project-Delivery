/**
 * KPI Card Component (Premium Design)
 * 
 * Displays a key performance indicator with icon, value, title, and trend
 */

import { TrendingUp, TrendingDown } from 'lucide-react';

export default function KPICard({ 
  icon: Icon, 
  value, 
  title, 
  trend = null, 
  trendUp = true,
  color = 'indigo',
  className = '' 
}) {
  const colorMap = {
    indigo: 'bg-indigo-500/10 text-indigo-400',
    emerald: 'bg-emerald-500/10 text-emerald-400',
    orange: 'bg-orange-500/10 text-orange-400',
    red: 'bg-red-500/10 text-red-400',
    purple: 'bg-purple-500/10 text-purple-400',
  };

  return (
    <div className={`bg-[#111118] border border-white/[0.06] rounded-2xl p-5 hover:border-white/10 transition-all ${className}`}>
      <div className={`inline-flex p-2 rounded-xl ${colorMap[color]}`}>
        <Icon size={20} />
      </div>
      
      <div className="mt-3">
        <div className="text-3xl font-bold text-white">{value}</div>
        <div className="text-slate-400 text-sm font-medium mt-1">{title}</div>
      </div>

      {trend && (
        <div className="mt-3 flex items-center gap-1">
          {trendUp ? (
            <TrendingUp size={14} className="text-emerald-400" />
          ) : (
            <TrendingDown size={14} className="text-red-400" />
          )}
          <span className={`text-xs font-medium ${trendUp ? 'text-emerald-400' : 'text-red-400'}`}>
            {trend}
          </span>
        </div>
      )}
    </div>
  );
}
