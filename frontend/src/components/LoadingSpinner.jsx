/**
 * Loading Spinner Component (Premium Design)
 * 
 * Modern animated spinner with optional loading message.
 * Sizes: sm (16px), md (24px), lg (32px)
 */

export default function LoadingSpinner({ size = 'md', message = 'Processing with Cerebras AI...' }) {
  const sizeMap = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className="flex items-center gap-3">
      <div className={`${sizeMap[size]} relative`}>
        <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20 border-t-indigo-500 animate-spin"></div>
      </div>
      {message && (
        <span className="text-slate-400 text-sm">{message}</span>
      )}
    </div>
  );
}
