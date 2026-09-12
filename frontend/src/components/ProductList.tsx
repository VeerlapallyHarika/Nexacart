import { Product } from '@/lib/types';
import ProductCard from './ProductCard';

interface ProductListProps {
  products: Product[];
  onSelect: (product: Product) => void;
  selectedProductId?: string;
}

export default function ProductList({ products, onSelect, selectedProductId }: ProductListProps) {
  if (products.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
      {products.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          onSelect={onSelect}
          isSelected={selectedProductId === product.id}
        />
      ))}
    </div>
  );
}
