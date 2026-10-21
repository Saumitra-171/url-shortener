// data: [{ date: "2026-10-21", clicks: 3 }, ...], one entry per day, oldest first.
const WIDTH = 640;
const HEIGHT = 220;
const PAD = { top: 16, right: 8, bottom: 28, left: 34 };

function dayLabel(iso) {
  // "2026-10-21T00:00:00" has no zone, so it is read as local midnight and prints the same date.
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function BarChart({ data }) {
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const max = Math.max(1, ...data.map((d) => d.clicks)); // never 0, so we never divide by zero
  const slot = innerW / data.length;                      // horizontal space per day
  const barW = Math.max(1, slot * 0.7);                   // leave a gap between bars
  const baseline = PAD.top + innerH;
  const total = data.reduce((sum, d) => sum + d.clicks, 0);

  // Label the first, middle and last day only, so the axis stays readable at 90 days.
  const last = data.length - 1;
  const labelled = [...new Set([0, Math.floor(last / 2), last])];

  return (
    <svg className="chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img"
         aria-label={`Clicks per day: ${total} clicks over ${data.length} days`}>
      <line className="axis" x1={PAD.left} x2={WIDTH - PAD.right} y1={baseline} y2={baseline} />
      <line className="axis" x1={PAD.left} x2={WIDTH - PAD.right} y1={PAD.top} y2={PAD.top} />
      <text className="tick" x={PAD.left - 6} y={PAD.top + 4} textAnchor="end">{max}</text>
      <text className="tick" x={PAD.left - 6} y={baseline + 4} textAnchor="end">0</text>

      {data.map((d, i) => {
        const h = (d.clicks / max) * innerH;
        const x = PAD.left + slot * i + (slot - barW) / 2;
        return (
          <g key={d.date}>
            <rect className="bar" x={x} y={baseline - h} width={barW} height={h} rx="1" />
            {/* A transparent full-height target, so days with 0 clicks still show a tooltip. */}
            <rect x={PAD.left + slot * i} y={PAD.top} width={slot} height={innerH} fill="transparent">
              <title>{`${dayLabel(d.date)}: ${d.clicks} ${d.clicks === 1 ? "click" : "clicks"}`}</title>
            </rect>
          </g>
        );
      })}

      {labelled.map((i) => (
        <text key={i} className="tick" y={HEIGHT - 8}
              x={i === 0 ? PAD.left : i === last ? WIDTH - PAD.right : PAD.left + slot * i + slot / 2}
              textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"}>
          {dayLabel(data[i].date)}
        </text>
      ))}
    </svg>
  );
}