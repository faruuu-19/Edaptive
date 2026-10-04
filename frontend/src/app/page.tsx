import { checkHealth } from "@/lib/api";

// Placeholder until the Home & Profile UI (Track C, Mid-1) lands in src/features/home-profile.
export default async function Home() {
  const backendUp = await checkHealth();
  return (
    <main style={{ padding: 24 }}>
      <h1>Edaptive</h1>
      <p>Backend: {backendUp ? "connected" : "not reachable (run `make dev-backend`)"}</p>
    </main>
  );
}
