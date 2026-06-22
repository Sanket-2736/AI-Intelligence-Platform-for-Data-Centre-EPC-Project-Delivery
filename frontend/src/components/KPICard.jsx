/**
 * KPI Card Component
 * 
 * Reusable card for displaying key performance indicators.
 * Includes trend indicator (up/down/neutral) and optional icon.
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function KPICard({
  title,
  value,
  subtitle,
  color = 'blue',
  icon: Icon,
  trend = null,
}) {
  const colorClasses = {
    red: 'bg-red-500/10 border-red-500/30 text-red-400',
    orange: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
    green: 'bg-green-500/10 border-green-500/30 text-green-400',
    blue: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    purple: 'bg-purple-500/10 border-purple-500/30 text-purple-400',
  };

  const getTrendIcon = () => {
    if (!trend) return null;
    if (trend === 'up') return <TrendingUp size={16} className="text-green-400" />;
    if (trend === 'down') return <TrendingDown size={16} className="text-red-400" />;
    return <Minus size={16} className="text-gray-400" />;
  };

  return (
    <div className={`${colorClasses[color]} border rounded-xl p-6 backdrop-blur-sm`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-sm font-medium text-gray-400 mb-1">{title}</p>
          <p className="text-3xl font-bold text-white">{value}</p>
        </div>
        {Icon && (
          <Icon size={24} className="text-gray-500 opacity-50" />
        )}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-400">{subtitle}</p>
        {getTrendIcon()}
      </div>
    </div>
  );
}
