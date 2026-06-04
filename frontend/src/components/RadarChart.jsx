import React, { useEffect, useState } from 'react';

const RadarChart = ({ data, size = 300 }) => {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    // Trigger animation after mount
    const timer = setTimeout(() => setAnimate(true), 100);
    return () => clearTimeout(timer);
  }, []);

  if (!data || data.length < 3) return null;

  const center = size / 2;
  const radius = size * 0.35; // Leave space for labels
  const numPoints = data.length;
  const angleStep = (Math.PI * 2) / numPoints;

  // Generate grid levels (0.2, 0.4, 0.6, 0.8, 1.0)
  const levels = [0.2, 0.4, 0.6, 0.8, 1];
  
  const getPoint = (value, index) => {
    // Math.PI / 2 subtracts 90 degrees so the first point is at the top
    const angle = index * angleStep - Math.PI / 2;
    const r = radius * (value / 100);
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle)
    };
  };

  // Build grid paths
  const grids = levels.map((level, i) => {
    const points = data.map((_, index) => {
      const p = getPoint(level * 100, index);
      return `${p.x},${p.y}`;
    }).join(' ');
    return (
      <polygon 
        key={`grid-${i}`} 
        points={points} 
        fill="none" 
        stroke="rgba(255,255,255,0.1)" 
        strokeWidth="1" 
      />
    );
  });

  // Build axis lines
  const axes = data.map((_, index) => {
    const p = getPoint(100, index);
    return (
      <line 
        key={`axis-${index}`} 
        x1={center} 
        y1={center} 
        x2={p.x} 
        y2={p.y} 
        stroke="rgba(255,255,255,0.1)" 
        strokeWidth="1" 
      />
    );
  });

  // Build data polygon
  const dataPoints = data.map((d, i) => {
    const val = animate ? d.value : 0;
    return getPoint(val, i);
  });
  
  const polygonPoints = dataPoints.map(p => `${p.x},${p.y}`).join(' ');

  // Build labels
  const labels = data.map((d, index) => {
    // Push labels slightly outside the 100% radius
    const p = getPoint(120, index);
    return (
      <text
        key={`label-${index}`}
        x={p.x}
        y={p.y}
        fill="#94a3b8" // slate-400
        fontSize="10"
        fontWeight="bold"
        textAnchor="middle"
        dominantBaseline="middle"
        className="transition-opacity duration-1000 delay-300"
        style={{ opacity: animate ? 1 : 0 }}
      >
        {d.subject}
      </text>
    );
  });

  return (
    <div className="relative flex justify-center items-center w-full h-full" style={{ minHeight: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible drop-shadow-xl">
        <defs>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <linearGradient id="polyGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(6, 182, 212, 0.6)" /> {/* cyan-500 */}
            <stop offset="100%" stopColor="rgba(6, 182, 212, 0.1)" />
          </linearGradient>
        </defs>

        {/* Background Grids */}
        <g>{grids}</g>
        <g>{axes}</g>

        {/* Data Polygon with Glow and Transition */}
        <polygon
          points={polygonPoints}
          fill="url(#polyGrad)"
          stroke="#06b6d4" /* cyan-500 */
          strokeWidth="2"
          filter="url(#glow)"
          className="transition-all duration-1000 ease-out"
        />

        {/* Data Dots */}
        {dataPoints.map((p, i) => (
          <circle
            key={`dot-${i}`}
            cx={p.x}
            cy={p.y}
            r="3"
            fill="#fff"
            stroke="#06b6d4"
            strokeWidth="2"
            className="transition-all duration-1000 ease-out delay-100"
            style={{ opacity: animate ? 1 : 0 }}
          />
        ))}

        {/* Labels */}
        {labels}
      </svg>
    </div>
  );
};

export default RadarChart;
