import { BrowserRouter as Router, Navigate, Routes, Route } from 'react-router-dom';
import { lazy, Suspense, type ReactNode } from 'react';

const Landing = lazy(() => import('./pages/Landing'));
const Session = lazy(() => import('./pages/Session'));
const Auth = lazy(() => import('./pages/Auth'));
const PatientDashboard = lazy(() => import('./pages/PatientDashboard'));
const DoctorDashboard = lazy(() => import('./pages/DoctorDashboard'));

function ProtectedRoute({ role, children }: { role: 'patient' | 'doctor'; children: ReactNode }) {
  const token = localStorage.getItem('access_token');
  const currentRole = localStorage.getItem('role');
  if (!token) return <Navigate to="/auth" replace />;
  if (currentRole !== role) {
    return <Navigate to={currentRole === 'doctor' ? '/doctor-dashboard' : '/patient-dashboard'} replace />;
  }
  return children;
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-bg-black text-white selection:bg-neon-purple selection:text-white">
        <Suspense fallback={<div className="min-h-screen bg-black flex items-center justify-center text-white">Loading...</div>}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/auth" element={<Auth />} />
            <Route path="/patient-dashboard" element={<ProtectedRoute role="patient"><PatientDashboard /></ProtectedRoute>} />
            <Route path="/doctor-dashboard" element={<ProtectedRoute role="doctor"><DoctorDashboard /></ProtectedRoute>} />
            <Route path="/session" element={<ProtectedRoute role="patient"><Session /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </div>
    </Router>
  );
}

export default App;
