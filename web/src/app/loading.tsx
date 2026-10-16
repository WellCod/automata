export default function Loading() {
  return (
    <div className="flex flex-col gap-3 px-6 py-6" aria-busy="true">
      <span className="sr-only">Carregando…</span>
      <div className="bg-muted h-3.5 w-48 animate-pulse rounded" />
      <div className="bg-muted h-3 w-72 animate-pulse rounded" />
    </div>
  );
}
