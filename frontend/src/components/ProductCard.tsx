import { Product } from '@/lib/types';

interface ProductCardProps {
  product: Product;
  onSelect: (product: Product) => void;
  isSelected?: boolean;
  actionLabel?: string;
}

export default function ProductCard({ product, onSelect, isSelected, actionLabel = 'Select' }: ProductCardProps) {
  const attrs = product.attributes || {};
  const isInStock = product.stock_quantity > 0;

  // Generic attribute formatting strategy
  const formatAttributeKey = (key: string) => {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const getBadges = () => {
    const badges: string[] = [];

    // Prioritized highlights
    if (attrs.battery_life_hours) {
      badges.push(`${attrs.battery_life_hours}hr Battery`);
    }
    if (attrs.noise_cancellation === true) {
      badges.push('Active Noise Cancelling');
    }
    if (attrs.wireless === true) {
      badges.push('Wireless');
    }
    if (attrs.ram_gb) {
      badges.push(`${attrs.ram_gb}GB RAM`);
    }
    if (attrs.storage_gb) {
      badges.push(`${attrs.storage_gb}GB Storage`);
    }

    // Secondary specs (up to 4 total)
    for (const [key, value] of Object.entries(attrs)) {
      if (badges.length >= 4) break;

      if (['battery_life_hours', 'noise_cancellation', 'wireless', 'ram_gb', 'storage_gb', 'brand', 'type'].includes(key)) {
        continue;
      }

      if (value === true) {
        badges.push(formatAttributeKey(key));
      } else if (typeof value === 'number' || (typeof value === 'string' && value.length < 16)) {
        let displayVal = value.toString();
        if (key.includes('weight_grams') && typeof value === 'number') displayVal += 'g';
        else if (key.includes('camera_mp') && typeof value === 'number') displayVal += 'MP';
        else if (key.includes('screen_size') && typeof value === 'number') displayVal += '"';

        badges.push(`${formatAttributeKey(key.replace(/_gb|_grams|_mp|_inches/, ''))}: ${displayVal}`);
      }
    }

    return badges;
  };

  const badges = getBadges();

  return (
    <div
      className={`rounded-2xl p-5 flex flex-col h-full transition-all duration-200 border ${
        isSelected
          ? 'border-accent bg-accent/5 ring-1 ring-accent shadow-md'
          : 'border-slopes/40 bg-white hover:border-mountainside/50 hover:shadow-lg'
      }`}
    >
      {/* Category / Brand pill */}
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <span className="text-[11px] font-semibold text-apres uppercase tracking-wider">
          {product.category?.replace('-', ' ')}
        </span>
        {attrs.brand && (
          <span className="text-xs font-medium text-mountainside bg-arctic-soft px-2 py-0.5 rounded-md border border-slopes/20">
            {attrs.brand}
          </span>
        )}
      </div>

      {/* Title and Price */}
      <div className="flex justify-between items-start mb-2.5 gap-3">
        <h4 className="font-bold text-midnight leading-snug line-clamp-2 text-base">
          {product.name}
        </h4>
        <span className="text-midnight font-extrabold whitespace-nowrap bg-arctic-soft px-2.5 py-1 rounded-lg border border-slopes/30 text-sm">
          ₹{product.price.toLocaleString('en-IN')}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-apres mb-4 line-clamp-2 flex-grow leading-relaxed">
        {product.description}
      </p>

      {/* Specs Badges */}
      <div className="flex flex-wrap gap-1.5 mb-5">
        {badges.map((badge, idx) => (
          <span
            key={idx}
            className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-arctic-soft text-mountainside border border-slopes/25"
          >
            {badge}
          </span>
        ))}
      </div>

      {/* Footer: Stock + Action */}
      <div className="flex items-center justify-between mt-auto pt-3.5 border-t border-slopes/20">
        <span
          className={`text-xs font-medium flex items-center gap-1.5 ${
            isInStock ? 'text-emerald-700' : 'text-rose-600'
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isInStock ? 'bg-emerald-500' : 'bg-rose-500'
            }`}
          />
          {isInStock ? `${product.stock_quantity} in stock` : 'Out of stock'}
        </span>

        <button
          onClick={() => onSelect(product)}
          disabled={!isInStock || isSelected}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            isSelected
              ? 'bg-accent/15 text-accent cursor-default border border-accent/30'
              : isInStock
              ? 'bg-midnight text-white hover:bg-mountainside hover:shadow-md hover:scale-[1.02] active:scale-[0.98]'
              : 'bg-slopes/30 text-apres cursor-not-allowed border border-slopes/30'
          }`}
        >
          {isSelected ? 'Selected' : actionLabel}
        </button>
      </div>
    </div>
  );
}
