import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import Session from './pages/Session';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-bg-black text-white selection:bg-neon-purple selection:text-white">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/session" element={<Session />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
