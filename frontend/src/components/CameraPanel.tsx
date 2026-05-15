import React, { forwardRef, useState, useCallback } from 'react';
import Webcam from 'react-webcam';
import { AlertTriangle } from 'lucide-react';

interface CameraPanelProps {
  onUserMedia?: () => void;
  onUserMediaError?: (error: string | DOMException) => void;
}

const CameraPanel = forwardRef<Webcam, CameraPanelProps>(({ onUserMedia, onUserMediaError }, ref) => {
  const [hasError, setHasError] = useState<string | null>(null);

  const handleUserMediaError = useCallback((error: string | DOMException) => {
    console.error("Camera Error:", error);
    setHasError(typeof error === 'string' ? error : error.message || "Camera access denied");
    if (onUserMediaError) onUserMediaError(error);
  }, [onUserMediaError]);

  const videoConstraints = {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    facingMode: "user"
  };

  if (hasError) {
    return (
      <div className="relative w-full h-full bg-gray-900 rounded-2xl overflow-hidden border border-red-500/30 shadow-2xl flex flex-col items-center justify-center text-center p-6">
        <div className="p-4 rounded-full bg-red-500/10 mb-4">
          <AlertTriangle className="w-12 h-12 text-red-500" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">Camera Access Error</h3>
        <p className="text-gray-400 mb-6 max-w-md">
          {hasError}. Please ensure you have granted camera permissions to this site.
        </p>
        <button 
          onClick={() => window.location.reload()}
          className="px-6 py-2 bg-white text-black rounded-full font-bold hover:bg-gray-200 transition-colors"
        >
          Reload Page
        </button>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-gray-900 rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
      <Webcam
        audio={false}
        ref={ref}
        screenshotFormat="image/jpeg"
        videoConstraints={videoConstraints}
        onUserMedia={onUserMedia}
        onUserMediaError={handleUserMediaError}
        className="w-full h-full object-cover"
        mirrored={true}
      />
      
      {/* Overlay UI */}
      <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-md px-3 py-1 rounded-full border border-neon-cyan/30 flex items-center gap-2 z-10">
        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
        <span className="text-xs font-mono text-neon-cyan tracking-wider">LIVE FEED</span>
      </div>
    </div>
  );
});

CameraPanel.displayName = 'CameraPanel';
export default CameraPanel;
