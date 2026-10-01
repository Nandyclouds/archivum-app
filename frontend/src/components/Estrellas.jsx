import { Star } from "lucide-react";

export function Estrellas({ rating, size = 16 }) {
  if (rating == null) return null;
  return (
    <span className="arv-stars">
      {Array.from({ length: 5 }).map((_, i) => {
        const llenado = Math.max(0, Math.min(1, rating - i)) * 100;
        return (
          <span key={i} className="arv-stars-star">
            <Star size={size} strokeWidth={1.75} />
            <span className="arv-stars-fill" style={{ width: `${llenado}%` }}>
              <Star size={size} strokeWidth={1.75} fill="currentColor" />
            </span>
          </span>
        );
      })}
    </span>
  );
}
