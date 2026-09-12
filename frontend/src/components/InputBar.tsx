'use client';

import { useState, FormEvent } from 'react';

interface InputBarProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export default function InputBar({ onSend, disabled }: InputBarProps) {
  const [input, setInput] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 p-4 bg-white">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask about products... (e.g., 'wireless headphones under ₹5,000')"
        disabled={disabled}
        className="flex-1 px-4 py-3 bg-arctic-soft/50 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/70 focus:outline-none focus:ring-2 focus:ring-midnight focus:border-transparent disabled:bg-slopes/20 transition-all"
      />
      <button
        type="submit"
        disabled={disabled || !input.trim()}
        className="px-6 py-3 bg-midnight text-white text-sm font-semibold rounded-xl hover:bg-mountainside focus:outline-none focus:ring-2 focus:ring-midnight focus:ring-offset-2 disabled:bg-slopes/40 disabled:text-apres disabled:cursor-not-allowed transition-all shadow-sm"
      >
        Send
      </button>
    </form>
  );
}
