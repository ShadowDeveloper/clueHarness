/** Candidate-count curves (mean envelope combinations remaining per turn, per agent label) as a bare SVG chart. */
const COLORS = ["#f0c419", "#4fb3ff", "#3fb950", "#e5484d", "#b366d9", "#ff9f43"];

export default function Curves({ curves, width = 520, height = 220 }: { curves: Record<string, number[]>; width?: number; height?: number }) {
  const labels = Object.keys(curves);
  if (!labels.length) return <div className="dim">no curves yet</div>;
  const maxX = Math.max(...labels.map((l) => curves[l].length)) - 1;
  const maxY = Math.max(1, ...labels.flatMap((l) => curves[l]));
  const pad = 32;
  const X = (i: number) => pad + (i / Math.max(1, maxX)) * (width - pad - 8);
  const Y = (v: number) => height - pad + 8 - (Math.log(v + 1) / Math.log(maxY + 1)) * (height - pad - 8);
  return (
    <svg width={width} height={height} role="img" aria-label="candidate count curves">
      <line x1={pad} y1={8} x2={pad} y2={height - pad + 8} stroke="#444" />
      <line x1={pad} y1={height - pad + 8} x2={width - 8} y2={height - pad + 8} stroke="#444" />
      {[1, 10, 100, 324].filter((v) => v <= maxY * 1.5).map((v) => <g key={v}><text x={pad - 4} y={Y(v) + 3} fontSize={10} fill="#8a919e" textAnchor="end">{v}</text><line x1={pad} y1={Y(v)} x2={width - 8} y2={Y(v)} stroke="#2a2f3a" /></g>)}
      <text x={width / 2} y={height - 4} fontSize={10} fill="#8a919e" textAnchor="middle">turn (own turns) — log scale of envelope candidates remaining</text>
      {labels.map((l, i) => (
        <g key={l}>
          <polyline fill="none" stroke={COLORS[i % COLORS.length]} strokeWidth={1.8} points={curves[l].map((v, j) => `${X(j)},${Y(v)}`).join(" ")} />
          <text x={width - 8} y={14 + i * 13} fontSize={11} fill={COLORS[i % COLORS.length]} textAnchor="end">{l}</text>
        </g>
      ))}
    </svg>
  );
}
