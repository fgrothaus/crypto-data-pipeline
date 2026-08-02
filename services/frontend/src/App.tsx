import { Routes, Route } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { CoinDetail } from './pages/CoinDetail';
import './App.css';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/coin/:coinId" element={<CoinDetail />} />
    </Routes>
  );
}

export default App;