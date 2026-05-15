import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Activity } from 'lucide-react';
import ThreeHero from '../components/ThreeHero';

export default function Landing() {
  return (
    <div className="relative w-full h-screen flex flex-col items-center justify-center overflow-hidden">
      {/* Background 3D Element */}
      <ThreeHero />

      <div className="z-10 text-center px-4 max-w-4xl mx-auto">
        <div className="mb-6 flex justify-center">
          <div className="p-3 rounded-full bg-white/5 border border-white/10 backdrop-blur-md">
            <Activity className="w-8 h-8 text-neon-cyan" />
          </div>
        </div>
        
        <h1 className="text-6xl md:text-8xl font-bold tracking-tighter mb-6">
          AI-PHYSIO <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-neon-purple to-neon-cyan">
            ASSISTANT
          </span>
        </h1>
        
        <p className="text-xl md:text-2xl text-gray-400 mb-10 max-w-2xl mx-auto font-light">
          Real-time pose analysis and feedback powered by computer vision.
          Correct your form instantly.
        </p>

        <Link 
          to="/session"
          className="group relative inline-flex items-center gap-3 px-8 py-4 bg-white text-black rounded-full text-lg font-bold tracking-wide hover:scale-105 transition-transform duration-200"
        >
          <span className="relative z-10">START LIVE SESSION</span>
          <ArrowRight className="w-5 h-5 relative z-10 group-hover:translate-x-1 transition-transform" />
          <div className="absolute inset-0 rounded-full bg-neon-cyan blur-lg opacity-50 group-hover:opacity-80 transition-opacity"></div>
        </Link>
      </div>

      <div className="absolute bottom-8 text-xs text-gray-600 font-mono">
        POWERED BY MEDIAPIPE • REACT • FASTAPI
      </div>
    </div>
  );
}
