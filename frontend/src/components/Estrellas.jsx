import { Star } from "lucide-react";

export function Estrellas({ rating, size = 16 }) {
  if (rating == null) return null;
  const porcentaje = Math.max(0, Math.min(100, (rating / 5) * 100));
  return (
    <span className="arv-stars">
      <span className="arv-stars-track">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star key={i} size={size} strokeWidth={1.75} />
        ))}
      </span>
      <span className="arv-stars-value" style={{ width: `${porcentaje}%` }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <Star key={i} size={size} strokeWidth={1.75} fill="currentColor" />
        ))}
      </span>
    </span>
  );
}
