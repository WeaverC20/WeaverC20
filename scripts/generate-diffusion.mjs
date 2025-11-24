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

  // precompute frame position strings for each particle
  const nParticles = frames[0].length;
  const particleKeyframes = Array.from({ length: nParticles }, (_, i) =>
    frames.map(f => {
      const p = f[i];
      const px = cellGap + p.x * (cellSize + cellGap);
      const py = cellGap + p.y * (cellSize + cellGap);
      return `${px.toFixed(2)},${py.toFixed(2)}`;
    })
  );

  const svgParts = [];

  svgParts.push(
`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <defs>
    <style>
      .cell { rx:2; ry:2; }
      .mol  { fill:${particleColor}; opacity:${particleOpacity}; }
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

  // particles as circles with animateMotion-like keyframes via <animate>
  for (let i = 0; i < nParticles; i++) {
    const pts = particleKeyframes[i];
    const values = pts.join(";");

    svgParts.push(
`  <circle class="mol" r="${(cellSize*0.28).toFixed(2)}">
    <animate attributeName="cx" dur="${durationSec}s" repeatCount="indefinite"
      values="${pts.map(v => v.split(",")[0]).join(";")}" keyTimes="${pts.map((_,k)=> (k/(pts.length-1)).toFixed(4)).join(";")}" />
    <animate attributeName="cy" dur="${durationSec}s" repeatCount="indefinite"
      values="${pts.map(v => v.split(",")[1]).join(";")}" keyTimes="${pts.map((_,k)=> (k/(pts.length-1)).toFixed(4)).join(";")}" />
  </circle>`
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