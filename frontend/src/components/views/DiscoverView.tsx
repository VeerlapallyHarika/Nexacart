import React, { useState, useEffect, useMemo } from 'react';
import { Product } from '@/lib/types';
import { fetchProducts } from '@/lib/api';
import ProductCard from '../ProductCard';
import LoadingSpinner from '../LoadingSpinner';

interface DiscoverViewProps {
  onAddToCart: (productId: string) => void;
}

export default function DiscoverView({ onAddToCart }: DiscoverViewProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    const loadProducts = async () => {
      try {
        setIsLoading(true);
        const data = await fetchProducts();
        setProducts(data);
      } catch (err) {
        console.error('Failed to load products:', err);
        setError('Failed to load products. Please try again later.');
      } finally {
        setIsLoading(false);
      }
    };

    loadProducts();
  }, []);

  const categories = useMemo(() => {
    const cats = new Set(products.map(p => p.category));
    return ['all', ...Array.from(cats)].sort();
  }, [products]);

  const filteredProducts = useMemo(() => {
    return products.filter(p => {
      const matchesCategory = selectedCategory === 'all' || p.category === selectedCategory;
      const matchesSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesCategory && matchesSearch;
    });
  }, [products, selectedCategory, searchQuery]);

  return (
    <div className="flex-1 overflow-y-auto bg-arctic-soft p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4 pb-6 border-b border-slopes/20">
          <div>
            <h1 className="text-3xl font-extrabold text-midnight tracking-tight">Discover Products</h1>
            <p className="text-apres text-sm mt-1">Explore our complete catalog of verified tech gear</p>
          </div>

          <div className="flex w-full md:w-auto gap-3">
            <div className="relative w-full md:w-80">
              <input
                type="text"
                placeholder="Search products, brands, specs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight focus:border-transparent transition-all shadow-sm"
              />
              <span className="absolute left-3.5 top-3 text-apres text-sm">🔍</span>
            </div>
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap gap-2 mb-8">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                selectedCategory === cat
                  ? 'bg-midnight text-white shadow-sm border border-midnight'
                  : 'bg-white text-mountainside border border-slopes/35 hover:bg-arctic-soft hover:border-mountainside/50'
              }`}
            >
              {cat === 'all'
                ? 'All Products'
                : cat.replace('-', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="flex justify-center items-center py-24">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <div className="bg-white border border-rose-200 text-rose-700 p-6 rounded-2xl text-center shadow-sm">
            {error}
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="bg-white p-12 rounded-2xl border border-slopes/30 text-center shadow-sm max-w-lg mx-auto my-12">
            <div className="w-16 h-16 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-4 text-2xl border border-slopes/20">
              🔍
            </div>
            <h3 className="text-lg font-bold text-midnight mb-1">No products found</h3>
            <p className="text-apres text-sm">Try adjusting your search terms or category filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {filteredProducts.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onSelect={() => onAddToCart(product.id)}
                actionLabel="Add to Cart"
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
