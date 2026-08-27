import "./App.css";

function App() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">CogniStream</h1>
        <p className="text-gray-500">
          Developer Flow-State & Cognitive Load Analytics
        </p>
      </header>

      <main>
        {/* Metric cards will go here (Commit 4) */}
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              Metric cards coming soon...
            </div>
          </div>
        </section>

        {/* Charts will go here (Commit 5-6) */}
        <section>
          <h2 className="text-xl font-semibold mb-3">
            Context-Switching Tax
          </h2>
          <div className="bg-white rounded-lg shadow p-4">
            Charts coming soon...
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;