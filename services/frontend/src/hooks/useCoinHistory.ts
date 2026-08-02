import { useState, useEffect } from 'react';

export interface PricePoint {
  timestamp: string;
  price_eur: number;
}

export const useCoinHistory = (coinId: string | null) => {
  const [history, setHistory] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!coinId) return;

    const fetchHistory = async () => {
      setLoading(true);
      try {
        const response = await fetch(`http://api.crypto.localhost/prices/history/${coinId}`);
        if (response.ok) {
          const data: PricePoint[] = await response.json();
          const formattedData = data.map((item) => ({
            ...item,
            formattedTime: new Date(item.timestamp).toLocaleTimeString('de-DE', {
                hour: '2-digit',
                minute: '2-digit',
            }),
            }));
          setHistory(formattedData);
        }
      } catch (error) {
        console.error("Fehler beim Laden der Historie:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [coinId]);

  return { history, loading };
};