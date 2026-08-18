/**
 * Resizes a video frame and converts it to a base64 JPEG string.
 * @param video The HTMLVideoElement source
 * @param width Target width (e.g. 960)
 * @returns Base64 string (without data:image/jpeg;base64, prefix if desired, but usually we send full string or strip it)
 */
export const captureFrame = (video: HTMLVideoElement, width: number = 960): string | null => {
    if (!video.videoWidth) return null;
  
    const scale = width / video.videoWidth;
    const height = video.videoHeight * scale;
  
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return null;
  
    ctx.drawImage(video, 0, 0, width, height);
    
    // Preserve arm and wrist detail; these landmarks are essential for V-W reps.
    return canvas.toDataURL('image/jpeg', 0.8);
  };
