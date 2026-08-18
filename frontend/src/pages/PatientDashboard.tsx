import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, BarChart3, ClipboardList, History, Play, Zap, Trophy } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { apiFetch, clearAuth } from '../lib/api';
import { buildDailyActivity } from '../lib/dailyActivity';

interface UserProfile {
  username: string;
  total_xp: number;
  current_streak: number;
  total_sessions: number;
  best_form_quality: number;
  last_session_date: string;
}

interface Session {
  session_id: string;
  date: string;
  duration: number;
  exercise_name: string;
  total_reps: number;
  form_quality: number;
  xp_earned: number;
}

interface PlanAssignment {
  assignment_id: string;
  doctor_username: string;
  notes: string;
  start_date: string;
  completed_sessions: number;
  plan: {
    planId: string;
    name: string;
    description: string;
    durationWeeks: number;
    exercises: Array<{ name: string; targetReps: number; targetSets: number }>;
  };
}

export default function PatientDashboard() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [assignments, setAssignments] = useState<PlanAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const userId = localStorage.getItem('user_id');
  const username = localStorage.getItem('username');

  useEffect(() => {
    if (!userId) {
      navigate('/auth');
      return;
    }

    const fetchData = async () => {
      try {
        const profileRes = await apiFetch(`/api/user/profile/${userId}`);
        if (!profileRes.ok) throw new Error('Unable to load profile');
        const profileData = await profileRes.json();
        setProfile(profileData);

        const sessionsRes = await apiFetch(`/api/user/sessions/${userId}`);
        if (!sessionsRes.ok) throw new Error('Unable to load sessions');
        const sessionsData = await sessionsRes.json();
        setSessions(sessionsData.sessions);

        const assignmentsRes = await apiFetch('/api/patient/assignments?active_only=true');
        if (assignmentsRes.ok) {
          const assignmentsData = await assignmentsRes.json();
          setAssignments(assignmentsData.assignments);
        }
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err instanceof Error ? err.message : 'Unable to load dashboard');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [userId, navigate]);

  const handleLogout = () => {
    clearAuth();
    navigate('/auth');
  };

  const startSession = (assignmentId?: string) => {
    navigate(assignmentId ? `/session?assignment=${encodeURIComponent(assignmentId)}` : '/session');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-neon-cyan border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-white">Loading profile...</p>
        </div>
      </div>
    );
  }

  const chartData = buildDailyActivity(sessions, 7);

  return (
    <div className="min-h-screen bg-black p-4 md:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <img src="/image.png" alt="re+active" className="h-12 mb-2" />
            <h1 className="text-3xl font-bold text-white">
              Welcome back, <span className="text-neon-cyan">{username}</span>
            </h1>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors"
          >
            <LogOut size={20} /> Logout
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {/* XP Card */}
          <div className="bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20 border border-neon-cyan/30 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Total XP</p>
                <p className="text-3xl font-bold text-neon-cyan">{profile?.total_xp || 0}</p>
              </div>
              <Zap className="text-neon-cyan opacity-50" size={32} />
            </div>
          </div>

          {/* Streak Card */}
          <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 border border-orange-500/30 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Current Streak</p>
                <p className="text-3xl font-bold text-orange-400">{profile?.current_streak || 0} days</p>
              </div>
              <Trophy className="text-orange-400 opacity-50" size={32} />
            </div>
          </div>

          {/* Sessions Card */}
          <div className="bg-gradient-to-br from-green-500/20 to-emerald-500/20 border border-green-500/30 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Total Sessions</p>
                <p className="text-3xl font-bold text-green-400">{profile?.total_sessions || 0}</p>
              </div>
              <History className="text-green-400 opacity-50" size={32} />
            </div>
          </div>

          {/* Best Form Card */}
          <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Best Form Quality</p>
                <p className="text-3xl font-bold text-purple-400">{profile?.best_form_quality.toFixed(0)}%</p>
              </div>
              <BarChart3 className="text-purple-400 opacity-50" size={32} />
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-red-300">{error}</div>
        )}

        {/* Therapist-assigned plans */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <ClipboardList className="text-neon-cyan" size={22} /> Assigned Recovery Plans
          </h2>
          {assignments.length === 0 ? (
            <p className="text-gray-400">No active therapist-assigned plan yet. You can still start a self-guided session.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {assignments.map((assignment) => (
                <div key={assignment.assignment_id} className="rounded-xl border border-neon-cyan/30 bg-neon-cyan/5 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-bold text-white text-lg">{assignment.plan.name}</h3>
                      <p className="text-sm text-gray-400">Assigned by {assignment.doctor_username}</p>
                    </div>
                    <span className="rounded-full bg-green-500/15 px-3 py-1 text-xs text-green-400">Active</span>
                  </div>
                  <p className="mt-3 text-sm text-gray-300">{assignment.notes || assignment.plan.description}</p>
                  <div className="mt-3 text-xs text-gray-400">
                    {assignment.plan.exercises.length} exercises • {assignment.completed_sessions} sessions completed
                  </div>
                  <button
                    onClick={() => startSession(assignment.assignment_id)}
                    className="mt-4 w-full rounded-lg bg-neon-cyan py-2.5 font-bold text-black hover:bg-cyan-300"
                  >
                    Start Prescribed Session
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Form Quality Chart */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-xl font-bold text-white">Daily Form Quality</h2>
            <p className="mb-4 text-xs text-gray-500">Average quality across sessions on each active day</p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="date" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #00d9ff' }}
                  labelStyle={{ color: '#fff' }}
                  labelFormatter={(_, payload) => {
                    const point = payload?.[0]?.payload;
                    return point ? `${point.fullDate} • ${point.sessionCount} session${point.sessionCount === 1 ? '' : 's'}` : '';
                  }}
                  formatter={(value) => [`${Number(value).toFixed(1)}%`, 'Average quality']}
                />
                <Line
                  type="monotone"
                  dataKey="averageQuality"
                  stroke="#00d9ff"
                  strokeWidth={2}
                  dot={{ fill: '#00d9ff' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Reps Chart */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-xl font-bold text-white">Daily Repetitions</h2>
            <p className="mb-4 text-xs text-gray-500">Total repetitions across sessions on each active day</p>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="date" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #00d9ff' }}
                  labelStyle={{ color: '#fff' }}
                  labelFormatter={(_, payload) => {
                    const point = payload?.[0]?.payload;
                    return point ? `${point.fullDate} • ${point.sessionCount} session${point.sessionCount === 1 ? '' : 's'}` : '';
                  }}
                  formatter={(value) => [Number(value), 'Total reps']}
                />
                <Bar dataKey="totalReps" fill="#00d9ff" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Sessions */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
          <h2 className="text-xl font-bold text-white mb-4">Recent Sessions</h2>
          <div className="space-y-3">
            {sessions.length === 0 ? (
              <p className="text-gray-400">No sessions yet. Start your first session!</p>
            ) : (
              sessions.slice(0, 5).map(session => (
                <div key={session.session_id} className="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
                  <div>
                    <p className="font-bold text-white">{session.exercise_name}</p>
                    <p className="text-sm text-gray-400">
                      {new Date(session.date).toLocaleString([], {
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                      })} • {session.total_reps} reps • {(session.duration / 60).toFixed(0)}m
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xl font-bold text-neon-cyan">{session.xp_earned} XP</p>
                    <p className="text-sm text-gray-400">{session.form_quality.toFixed(0)}% form</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Start Session Button */}
        <button
          onClick={() => startSession()}
          className="w-full py-4 bg-gradient-to-r from-neon-cyan to-neon-purple text-white font-bold rounded-xl hover:opacity-90 transition-opacity flex items-center justify-center gap-2 text-lg"
        >
          <Play size={24} /> Start New Session
        </button>
      </div>
    </div>
  );
}
