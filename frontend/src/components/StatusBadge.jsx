/**
 * Status Badge Component
 * 
 * Displays status with color coding and optional dot indicator.
 * Maps various status types: GREEN|AMBER|RED|CRITICAL|MAJOR|MINOR|PASS|FAIL|ON_TRACK|AT_RISK
 */

export default function StatusBadge({ status }) {
  const statusMap = {
    // Health status
    GREEN: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30' },
    AMBER: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    RED: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
    
    // Severity levels
    CRITICAL: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
    MAJOR: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30' },
    MINOR: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    OBSERVATION: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
    
    // Test results
    PASS: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30' },
    FAIL: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
    CONDITIONAL_PASS: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    
    // Shipment status
    ON_TRACK: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30' },
    AT_RISK: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30' },
    DELAYED: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
  };

  const style = statusMap[status?.toUpperCase()] || statusMap.OBSERVATION;
  const label = status?.replace(/_/g, ' ').toUpperCase() || 'UNKNOWN';

  return (
    <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold border ${style.bg} ${style.text} ${style.border}`}>
      <span className={`w-2 h-2 rounded-full ${style.bg.replace('0/20', '0/100')}`}></span>
      {label}
    </span>
  );
}
