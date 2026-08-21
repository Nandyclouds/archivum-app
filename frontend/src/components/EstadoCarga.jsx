export function Cargando() {
  return <p className="arv-muted">Cargando…</p>;
}

export function ErrorCarga({ error, onReintentar }) {
  return (
    <div className="arv-card">
      <p className="arv-muted">No se pudo conectar con la API: {error.message}</p>
      {onReintentar && (
        <button className="arv-btn arv-btn-secondary" onClick={onReintentar}>
          Reintentar
        </button>
      )}
    </div>
  );
}

export function Vacio({ children }) {
  return <div className="arv-empty">{children}</div>;
}
