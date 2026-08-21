export function Estrellas({ rating }) {
  if (rating == null) return null;
  const redondeado = Math.round(rating * 2) / 2;
  const llenas = Math.floor(redondeado);
  const media = redondeado - llenas === 0.5;
  const vacias = 5 - llenas - (media ? 1 : 0);
  const texto = "★".repeat(llenas) + (media ? "½" : "") + "☆".repeat(vacias);
  return <span className="arv-stars">{texto}</span>;
}
