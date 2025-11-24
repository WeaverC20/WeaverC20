// scripts/generate-diffusion.mjs
import fs from "node:fs";
import path from "node:path";

const USERNAME = process.env.GITHUB_USER || process.env.GITHUB_REPOSITORY_OWNER;
const TOKEN = process.env.GITHUB_TOKEN; // provided by Actions

if (!USERNAME) throw new Error("Missing username");
if (!TOKEN) throw new Error("Missing GITHUB_TOKEN");

const GRAPHQL = "https://api.github.com/graphql";

async function fetchContribGrid() {
  const query = `
    query($login:String!) {
      user(login:$login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
  `;

  const res = await fetch(GRAPHQL, {
    method: "POST",
    headers: {
      "Authorization": `bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, variables: { login: USERNAME } }),
  });

  const json = await res.json();
  if (json.errors) throw new Error(JSON.stringify(json.errors, null, 2));

  const weeks = json.data.user.contributionsCollection.contributionCalendar.weeks;
  // flatten to columns (weeks) of 7 days each
  return weeks.map(w => w.contributionDays.map(d => d.contributionCount));
}

function randnBoxMuller() {
  // small gaussian noise for nicer motion
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function simulateParticles(grid, opts) {
  const {
    steps = 120,          // frames
    dt = 1.0,
    biasRight = 0.04,     // drift to the right
    jitter = 0.25,        // random walk strength
    radius = 0.28,        // particle radius in "cell units"
    maxPerCell = 3,       // cap particles per cell
  } = opts;

  const cols = grid.length;     // ~52
  const rows = grid[0].length;  // 7

  // seed particles on left side based on contributions
  const particles = [];
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const count = grid[c][r];
      const n = Math.min(maxPerCell, Math.round(Math.sqrt(count)));
      for (let k = 0; k < n; k++) {
        particles.push({
          x: c + 0.5 + 0.1 * randnBoxMuller(),
          y: r + 0.5 + 0.1 * randnBoxMuller(),
          vx: 0,
          vy: 0,
        });
      }
    }
  }

  // keep only those in the left ~25% of grid at t=0 (your "source side")
  const sourceCutoff = Math.max(2, Math.floor(cols * 0.25));
  const seeded = particles.filter(p => p.x < sourceCutoff);

  const frames = [];
  for (let t = 0; t < steps; t++) {
    // basic random-walk + drift
    for (const p of seeded) {
      p.vx = biasRight + jitter * randnBoxMuller();
      p.vy = jitter * randnBoxMuller();

      p.x += p.vx * dt;
      p.y += p.vy * dt;

      // reflect off boundaries
      if (p.x < 0.1) { p.x = 0.1; p.vx *= -0.6; }
      if (p.x > cols - 0.1) { p.x = cols - 0.1; p.vx *= -0.6; }
      if (p.y < 0.1) { p.y = 0.1; p.vy *= -0.6; }
      if (p.y > rows - 0.1) { p.y = rows - 0.1; p.vy *= -0.6; }
    }

    // soft collisions (cheap O(n^2) ok for small n)
    for (let i = 0; i < seeded.length; i++) {
      for (let j = i + 1; j < seeded.length; j++) {
        const a = seeded[i], b = seeded[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d2 = dx*dx + dy*dy;
        const minD = 2*radius;
        if (d2 < minD*minD && d2 > 1e-6) {
          const d = Math.sqrt(d2);
          const overlap = (minD - d) / 2;
          const nx = dx / d, ny = dy / d;
          a.x -= overlap * nx; a.y -= overlap * ny;
          b.x += overlap * nx; b.y += overlap * ny;
        }
      }
    }

    frames.push(seeded.map(p => ({ x: p.x, y: p.y })));
  }

  return { frames, cols, rows };
}

function colorForCount(count) {
  // GitHub-like 5-level shading
  if (count === 0) return "#ebedf0";
  if (count < 3)   return "#9be9a8";
  if (count < 7)   return "#40c463";
  if (count < 15)  return "#30a14e";
  return "#216e39";
}

function buildAnimatedSVG(grid, sim, opts) {
  const {
    cellSize = 12,
    cellGap = 2,
    durationSec = 3.0, // 2–5s target
    particleColor = "#58a6ff",
    particleOpacity = 0.9,
  } = opts;

  const { frames, cols, rows } = sim;
  const width  = cols * (cellSize + cellGap) + cellGap;
  const height = rows * (cellSize + cellGap) + cellGap;

  const nParticles = frames[0].length;

  // Convert cell-space positions to pixel-space
  function toPx(p) {
    return {
      x: cellGap + p.x * (cellSize + cellGap),
      y: cellGap + p.y * (cellSize + cellGap),
    };
  }

  // Build CSS keyframes for each particle
  const keyframesCSS = [];
  for (let i = 0; i < nParticles; i++) {
    const kf = [];
    for (let t = 0; t < frames.length; t++) {
      const pct = (t / (frames.length - 1)) * 100;
      const p = toPx(frames[t][i]);
      kf.push(`${pct.toFixed(2)}% { transform: translate(${p.x.toFixed(2)}px, ${p.y.toFixed(2)}px); }`);
    }
    keyframesCSS.push(`
      @keyframes mol-${i} {
        ${kf.join("\n")}
      }
      .mol-${i} { animation: mol-${i} ${durationSec}s linear infinite; }
    `);
  }

  const svgParts = [];

  svgParts.push(
`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <defs>
    <style>
      .cell { rx:2; ry:2; }
      .mol { fill:${particleColor}; opacity:${particleOpacity}; }
      ${keyframesCSS.join("\n")}
    </style>
  </defs>

  <!-- contribution lattice -->`
  );

  // draw grid
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const count = grid[c][r];
      const x = cellGap + c * (cellSize + cellGap);
      const y = cellGap + r * (cellSize + cellGap);
      svgParts.push(
`  <rect class="cell" x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="${colorForCount(count)}"/>`
      );
    }
  }

  svgParts.push("\n  <!-- molecules -->");

  const rPx = (cellSize * 0.28).toFixed(2);
  for (let i = 0; i < nParticles; i++) {
    // circles start at (0,0) inside a translated group
    svgParts.push(
`  <g class="mol mol-${i}">
      <circle cx="0" cy="0" r="${rPx}"></circle>
  </g>`
    );
  }

  svgParts.push("\n</svg>");
  return svgParts.join("\n");
}

async function main() {
  const grid = await fetchContribGrid();

  const sim = simulateParticles(grid, {
    steps: 120,
    biasRight: 0.05,
    jitter: 0.22,
    radius: 0.28,
    maxPerCell: 3,
  });

  const svg = buildAnimatedSVG(grid, sim, {
    durationSec: 3.2,  // tweak 2.0–5.0
  });

  const outDir = path.resolve("output");
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "diffusion.svg"), svg, "utf8");

  console.log(`wrote output/diffusion.svg with ${sim.frames[0].length} particles`);
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});