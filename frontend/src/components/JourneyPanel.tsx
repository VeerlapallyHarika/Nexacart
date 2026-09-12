import { JourneyState } from '@/lib/types';

interface JourneyPanelProps {
  journeyState: JourneyState;
}

const stages = [
  { id: 'intent' as const, label: 'Intent', icon: '🔍', description: 'Understand requirements' },
  { id: 'discovery' as const, label: 'Discovery', icon: '📦', description: 'Search & rank catalog' },
  { id: 'decision' as const, label: 'Decision', icon: '✨', description: 'Product selected' },
  { id: 'cart' as const, label: 'Cart', icon: '🛒', description: 'Verified basket' },
  { id: 'payment' as const, label: 'Payment', icon: '💳', description: 'Safe checkout' },
];

export default function JourneyPanel({ journeyState }: JourneyPanelProps) {
  return (
    <div className="w-80 bg-white border-l border-slopes/30 p-6 h-full flex flex-col justify-start overflow-y-auto">
      <div className="mb-6 pb-4 border-b border-slopes/20">
        <h3 className="text-xs font-bold text-midnight uppercase tracking-wider">
          Commerce Journey
        </h3>
        <p className="text-apres text-[11px] mt-0.5">Real-time state tracking</p>
      </div>

      <div className="space-y-4">
        {stages.map((stage, index) => {
          const state = journeyState[stage.id];
          return (
            <div key={stage.id} className="flex items-start gap-3.5 relative">
              {/* Connector line */}
              {index < stages.length - 1 && (
                <div
                  className={`absolute top-9 left-4.5 w-0.5 h-6 -ml-[1px] transition-colors ${
                    state === 'completed' ? 'bg-midnight' : 'bg-slopes/30'
                  }`}
                />
              )}

              {/* Status Circle */}
              <div
                className={`w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 transition-all border ${
                  state === 'completed'
                    ? 'bg-midnight text-white border-midnight shadow-xs'
                    : state === 'active'
                    ? 'bg-accent text-white border-accent shadow-sm animate-pulse'
                    : 'bg-arctic-soft text-apres border-slopes/30'
                }`}
              >
                {state === 'completed' ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                ) : (
                  stage.icon
                )}
              </div>

              {/* Text */}
              <div className="flex-1 pt-0.5">
                <span
                  className={`text-xs font-bold block ${
                    state === 'completed'
                      ? 'text-midnight'
                      : state === 'active'
                      ? 'text-accent'
                      : 'text-apres'
                  }`}
                >
                  {stage.label}
                </span>
                <p
                  className={`text-[11px] mt-0.5 leading-snug ${
                    state === 'completed'
                      ? 'text-apres'
                      : state === 'active'
                      ? 'text-midnight font-medium'
                      : 'text-slopes-dark'
                  }`}
                >
                  {stage.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
