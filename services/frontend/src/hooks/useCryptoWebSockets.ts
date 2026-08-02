import { useState, useEffect } from 'react';

export interface CoinMetrics {
  eur: number;
  eur_24h_change: number;
}

export interface CryptoDataPayload {
  coins: {
    [coinName: string]: CoinMetrics;
  };
}

export const useCryptoWebSocket = (url: string) => {
  const [data, setData] = useState<CryptoDataPayload | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);

  useEffect(() => {
    let isComponentMounted = true;
    const socket = new WebSocket(url);

    socket.onopen = () => {
      if (!isComponentMounted) return;
      setIsConnected(true);
      console.log("Websocket-Verbindung erfolgreich initialisiert.");
    };

    socket.onmessage = (event) => {
      if (!isComponentMounted) return;
      try {
        const parsedData: CryptoDataPayload = JSON.parse(event.data);
        setData(parsedData);
      } catch (error) {
        console.error("Fehler beim Parsen der WebSocket Daten:", error);
      }
    };

    socket.onclose = (event) => {
      if (!isComponentMounted) return;
      setIsConnected(false);
      console.log("WebSocket-Verbindung geschlossen.");
    };

    socket.onerror = (error) => {
      if (isComponentMounted && socket.readyState !== WebSocket.CLOSED) {
        console.error('WebSocket-Fehler aufgetreten:', error);
      }
    };

    return () => {
      isComponentMounted = false;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    };
  }, [url]);

  return { data, isConnected };
};