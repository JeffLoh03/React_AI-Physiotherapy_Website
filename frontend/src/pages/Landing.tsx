import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, LogIn, UserPlus } from 'lucide-react';
import ThreeHero from '../components/ThreeHero';

export default function Landing() {
  return (
    <div className="relative w-full h-screen flex flex-col items-center justify-center overflow-hidden">
      {/* Background 3D Element */}
      <ThreeHero />

      <div className="relative z-10 grid w-full max-w-7xl items-center px-6 lg:grid-cols-2 lg:px-10">
        <div className="text-center lg:text-left">
        <div className="mb-8 flex justify-center lg:justify-start">
          <img
            src="/image.png"
            alt="re+active logo"
            className="h-20 md:h-24 object-contain"
          />
        </div>
        
        <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-6">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-neon-purple to-neon-cyan">
            REHABILITATION
          </span> <br />
          <span className="text-white">AI ASSISTANT</span>
        </h1>
        
        <p className="text-xl md:text-2xl text-gray-400 mb-10 max-w-2xl mx-auto lg:mx-0 font-light">
          Personalized recovery plans. Real-time form correction. Your path to wellness.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
          <Link
            to="/auth?mode=login"
            className="group relative inline-flex items-center gap-3 px-8 py-4 bg-white text-black rounded-full text-lg font-bold tracking-wide hover:scale-105 transition-transform duration-200"
          >
            <LogIn className="w-5 h-5 relative z-10" />
            <span className="relative z-10">SIGN IN</span>
            <ArrowRight className="w-5 h-5 relative z-10 group-hover:translate-x-1 transition-transform" />
            <div className="absolute inset-0 rounded-full bg-neon-cyan blur-lg opacity-50 group-hover:opacity-80 transition-opacity"></div>
          </Link>

          <Link
            to="/auth?mode=register"
            className="group relative inline-flex items-center gap-3 px-8 py-4 bg-neon-purple/20 text-neon-cyan border border-neon-cyan rounded-full text-lg font-bold tracking-wide hover:bg-neon-purple/40 transition-all duration-200"
          >
            <UserPlus className="w-5 h-5 relative z-10" />
            <span className="relative z-10">REGISTER</span>
            <ArrowRight className="w-5 h-5 relative z-10 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
        </div>
        <div className="hidden min-h-[560px] lg:block" aria-hidden="true" />
      </div>

      <div className="absolute bottom-8 text-xs text-gray-600 font-mono">
        re+active • POWERED BY MEDIAPIPE • REACT • FASTAPI
      </div>
    </div>
  );
}
