import React from "react";
import {motion} from "motion/react";

const RADIUS = 32;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS; // ≈ 201.06

export function scoreToDashOffset(score: number): number {
  const clamped = Math.max(0, Math.min(100, score));
  return CIRCUMFERENCE * (1 - clamped / 100);
}

export default function CircularGauge({
  score,
  label,
  stroke = "#06b6d4",
  textClass = "text-cyan-400",
}: {
  score: number;
  label: string;
  stroke?: string;
  textClass?: string;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const offset = scoreToDashOffset(clamped);

  return (
    <div className="flex-1 max-w-28 h-20 relative flex items-center justify-center">
      <svg className="w-20 h-20 transform -rotate-90" viewBox="0 0 80 80" aria-hidden>
        <circle
          cx="40"
          cy="40"
          r={RADIUS}
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="6"
          fill="transparent"
        />
        <motion.circle
          cx="40"
          cy="40"
          r={RADIUS}
          stroke={stroke}
          strokeWidth="6"
          fill="transparent"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          initial={false}
          animate={{strokeDashoffset: offset}}
          transition={{duration: 0.85, ease: "easeInOut"}}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <motion.span
          key={clamped}
          className={`${textClass} font-extrabold text-base leading-none`}
          initial={{opacity: 0.4, scale: 0.92}}
          animate={{opacity: 1, scale: 1}}
          transition={{duration: 0.35}}
        >
          {clamped}
        </motion.span>
        <span className="text-[7px] text-slate-500 uppercase leading-none mt-0.5 font-sans">{label}</span>
      </div>
    </div>
  );
}
