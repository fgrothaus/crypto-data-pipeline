import { useParams, useNavigate } from 'react-router-dom';
import { useCoinHistory } from '../hooks/useCoinHistory';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export function CoinDetail() {
  const { coinId } = useParams<{ coinId: string }>();
  const navigate = useNavigate();
  const { history, loading } = useCoinHistory(coinId || null);

  return (
    <div className="app-container">
      <header style={{ marginBottom: '20px' }}>
        <button 
          onClick={() => navigate('/')}
          style={{
            padding: '8px 16px',
            background: '#2a2a3c',
            color: '#fff',
            border: '1px solid #444',
            borderRadius: '6px',
            cursor: 'pointer',
            marginBottom: '15px'
          }}
        >
          ← Zurück zur Übersicht
        </button>
        <h1>Historie: {coinId?.toUpperCase()}</h1>
      </header>

      <main>
        <div style={{ background: '#1e1e2e', padding: '24px', borderRadius: '12px', minHeight: '400px' }}>
          {loading ? (
            <p style={{ color: '#aaa' }}>Lade historische Daten aus Postgres...</p>
          ) : history.length === 0 ? (
            <p style={{ color: '#aaa' }}>Keine Historien-Daten verfügbar.</p>
          ) : (
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={history}>
                <XAxis dataKey="formattedTime" stroke="#8884d8" />
                <YAxis domain={['auto', 'auto']} stroke="#8884d8" />
                <Tooltip
                    contentStyle={{ backgroundColor: '#2a2a3c', borderColor: '#444', color: '#fff' }}
                    formatter={(value: number) => [
                        value.toLocaleString('de-DE', {
                        style: 'currency',
                        currency: 'EUR',
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 6,
                        }),
                        'Preis'
                    ]}
                />
                <Line type="monotone" dataKey="price_eur" stroke="#82ca9d" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </main>
    </div>
  );
}