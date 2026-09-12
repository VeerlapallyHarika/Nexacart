'use client';

import { useEffect, useRef } from 'react';
import { ChatMessage, Product } from '@/lib/types';
import MessageBubble from './MessageBubble';
import ProductList from './ProductList';

interface ChatWindowProps {
  messages: ChatMessage[];
  onProductSelect: (product: Product) => void;
}

export default function ChatWindow({ messages, onProductSelect }: ChatWindowProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-5 bg-arctic-soft/40">
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-center p-6">
          <div className="w-14 h-14 bg-midnight border border-mountainside text-white rounded-2xl flex items-center justify-center mb-4 shadow-sm">
            <span className="font-bold text-2xl">N</span>
          </div>
          <h2 className="text-xl font-bold text-midnight mb-2">
            Welcome to NexaCart
          </h2>
          <p className="text-apres text-sm max-w-md">
            Ask me about products. Try: &quot;I need wireless headphones under 5,000 with long battery life&quot;
          </p>
        </div>
      ) : (
        <>
          {messages.map((message) => (
            <div key={message.id} className="mb-4">
              <MessageBubble message={message} />
              {message.products && message.products.length > 0 && (
                <div className="pl-11 pr-2 my-2">
                  <ProductList
                    products={message.products}
                    onSelect={onProductSelect}
                    selectedProductId={message.selectedProductId}
                  />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
}
