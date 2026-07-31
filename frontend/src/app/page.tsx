export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold">Atlas</h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Algorithmic trading platform
      </p>
      <div className="mt-8">
        <a
          href="/dashboard"
          className="rounded-md bg-primary px-6 py-3 text-primary-foreground hover:bg-primary/90"
        >
          Open Dashboard
        </a>
      </div>
    </main>
  );
}
