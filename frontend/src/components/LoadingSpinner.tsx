export default function LoadingSpinner() {
  return (
    <div className="flex justify-start mb-4 items-center gap-2.5">
      <div className="w-8 h-8 rounded-xl bg-midnight border border-mountainside text-white flex items-center justify-center text-xs font-bold shrink-0 shadow-2xs">
        ✨
      </div>
      <div className="bg-white border border-slopes/35 rounded-2xl px-4 py-2.5 shadow-2xs">
        <div className="flex items-center gap-2.5">
          <div className="flex space-x-1.5">
            <div className="w-1.5 h-1.5 bg-midnight rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-1.5 h-1.5 bg-mountainside rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-1.5 h-1.5 bg-apres rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-xs font-medium text-apres">AI is thinking & evaluating catalog...</span>
        </div>
      </div>
    </div>
  );
}
