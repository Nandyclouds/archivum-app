import { useState } from "react";
import { Star } from "lucide-react";

function valorDesdeClic(e, indice) {
  const rect = e.currentTarget.getBoundingClientRect();
  const esMitad = e.clientX - rect.left < rect.width / 2;
  return Math.max(1, indice + (esMitad ? 0.5 : 1));
}

export function EstrellasInput({ value, onChange, size = 28 }) {
  const [hover, setHover] = useState(null);
  const mostrado = hover ?? value;

  return (
    <div className="arv-stars-input" onMouseLeave={() => setHover(null)}>
      {Array.from({ length: 5 }).map((_, i) => {
        const llenado = Math.max(0, Math.min(1, mostrado - i)) * 100;
        return (
          <button
            type="button"
            key={i}
            className="arv-stars-input-star"
            onMouseMove={(e) => setHover(valorDesdeClic(e, i))}
            onClick={(e) => onChange(valorDesdeClic(e, i))}
            aria-label={`${i + 1}`}
          >
            <Star size={size} strokeWidth={1.75} className="arv-stars-input-track" />
            <span className="arv-stars-input-fill" style={{ width: `${llenado}%` }}>
              <Star size={size} strokeWidth={1.75} fill="currentColor" />
            </span>
          </button>
        );
      })}
    </div>
  );
}
