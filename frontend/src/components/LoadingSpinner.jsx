/**
 * Loading Spinner Component
 * 
 * Animated spinner with optional loading message.
 * Sizes: sm (16px), md (24px), lg (32px)
 */

export default function LoadingSpinner({ size = 'md', message = 'Processing with Cerebras AI...' }) {
  const sizeMap = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className={`${sizeMap[size]} animate-spin`}>
        <div className="relative w-full h-full">
          <div className="absolute inset-0 rounded-full border-2 border-gray-700"></div>
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 border-r-blue-500 animate-spin"></div>
        </div>
      </div>
      {message && (
        <p className="text-sm text-gray-400 animate-pulse">{message}</p>
      )}
    </div>
  );
}
