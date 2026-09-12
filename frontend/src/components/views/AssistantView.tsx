import React from 'react';
import ChatWindow from '../ChatWindow';
import InputBar from '../InputBar';
import JourneyPanel from '../JourneyPanel';
import LoadingSpinner from '../LoadingSpinner';
import { ChatMessage, JourneyState, Product } from '@/lib/types';

interface AssistantViewProps {
  messages: ChatMessage[];
  isLoading: boolean;
  journeyState: JourneyState;
  onSend: (message: string) => void;
  onProductSelect: (product: Product) => void;
}

export default function AssistantView({ 
  messages, 
  isLoading, 
  journeyState, 
  onSend, 
  onProductSelect 
}: AssistantViewProps) {
  
  return (
    <div className="flex-1 flex overflow-hidden bg-arctic-soft">
      <div className="flex-1 flex flex-col h-full border-r border-slopes/30 bg-white">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center overflow-y-auto bg-arctic-soft/30">
            <div className="w-14 h-14 bg-midnight text-white border border-mountainside rounded-2xl flex items-center justify-center mb-5 shadow-sm">
              <span className="text-2xl">✨</span>
            </div>
            <h2 className="text-2xl font-bold text-midnight mb-2 tracking-tight">AI Shopping Assistant</h2>
            <p className="text-apres text-sm max-w-md mb-8 leading-relaxed">
              Ask questions, specify budgets, or describe what you need. I'll search catalog products and help you decide with deterministic safety.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl text-left">
              <button 
                onClick={() => onSend("Find me a laptop under ₹70,000 for coding")}
                className="p-4 bg-white hover:bg-arctic-soft border border-slopes/40 hover:border-mountainside/50 rounded-xl transition-all text-xs font-medium text-midnight shadow-2xs hover:shadow-xs group"
              >
                <span className="text-apres group-hover:text-midnight">💡 </span>
                "Find me a laptop under ₹70,000 for coding"
              </button>
              <button 
                onClick={() => onSend("I need headphones with 40-hour battery")}
                className="p-4 bg-white hover:bg-arctic-soft border border-slopes/40 hover:border-mountainside/50 rounded-xl transition-all text-xs font-medium text-midnight shadow-2xs hover:shadow-xs group"
              >
                <span className="text-apres group-hover:text-midnight">🎧 </span>
                "I need headphones with 40-hour battery"
              </button>
              <button 
                onClick={() => onSend("Show me a phone with a good camera under ₹30,000")}
                className="p-4 bg-white hover:bg-arctic-soft border border-slopes/40 hover:border-mountainside/50 rounded-xl transition-all text-xs font-medium text-midnight shadow-2xs hover:shadow-xs group"
              >
                <span className="text-apres group-hover:text-midnight">📱 </span>
                "Show me a phone with a good camera under ₹30,000"
              </button>
              <button 
                onClick={() => onSend("What's the best mechanical keyboard?")}
                className="p-4 bg-white hover:bg-arctic-soft border border-slopes/40 hover:border-mountainside/50 rounded-xl transition-all text-xs font-medium text-midnight shadow-2xs hover:shadow-xs group"
              >
                <span className="text-apres group-hover:text-midnight">⌨️ </span>
                "What's the best mechanical keyboard?"
              </button>
            </div>
          </div>
        ) : (
          <ChatWindow messages={messages} onProductSelect={onProductSelect} />
        )}
        
        {isLoading && (
          <div className="px-6 py-2 bg-white flex items-center justify-center">
            <LoadingSpinner />
          </div>
        )}
        
        <div className="bg-white border-t border-slopes/25">
          <InputBar onSend={onSend} disabled={isLoading} />
        </div>
      </div>
      
      <div className="hidden lg:block w-80 flex-shrink-0">
        <JourneyPanel journeyState={journeyState} />
      </div>
    </div>
  );
}
