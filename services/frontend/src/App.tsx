import { useCryptoWebSocket } from './hooks/useCryptoWebSockets';
import './App.css';

function App() {

  const { data, isConnected } = useCryptoWebSocket('ws://api.crypto.localhost/ws/prices');

  return (
    <div className="app-container">
      <header>
        <h1>Crypto Live Dashboard</h1>
        <div className={`status-badge ${isConnected ? 'connected' : 'disconnected'}`}>
          Status: {isConnected ? 'Verbunden' : 'Getrennt'}
        </div>
      </header>

      <main>
        {!data ? (
          <div className="loading">Warte auf Live-Daten aus der Pipeline...</div>
        ) : (
          <div className="crypto-grid">
            {Object.entries(data.coins).map(([coinName, metrics]) => (
              <div key={coinName} className="crypto-card">
                <h2 className="coin-name">{coinName.toUpperCase()}</h2>
                
                <p className="coin-price">
                  {metrics.eur.toLocaleString('de-DE', {
                    style: 'currency',
                    currency: 'EUR',
                  })}
                </p>
                
                <p className={`coin-change ${metrics.eur_24h_change >= 0 ? 'positive' : 'negative'}`}>
                  {metrics.eur_24h_change >= 0 ? '▲' : '▼'}{' '}
                  {metrics.eur_24h_change.toFixed(2)}% (24h)
                </p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
