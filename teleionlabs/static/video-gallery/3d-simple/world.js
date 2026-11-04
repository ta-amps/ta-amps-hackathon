// The simple 3D set for the Teleion Labs film: one Durable Tasks database, one Durable Task Objects database, one
// OmniNode, and later a room of real Eranos pages. Every frame depends only on the film clock t, so seeking is exact.
// No sentence lives here: words come from film-words in the page, and film.js draws all text.
import * as T from "./three-0.187.0.min.js";

const PAPER = "#F5F2EA", CARD = "#FFFDF8", INK = "#11161F", BLUE = "#24519B", RUST = "#A23E1C", TONE = "#EFEBDF";
const READY = "#AFC4E6", WAIT = "#DDD6C7", DONE = BLUE, LOST = RUST, OBJ = "#D3AE9C", OBJ_ON = RUST, QUIET = "#CFC8B8", GREY = "#6B7078", PALE = "#C9D7EE";
const clamp = (x) => Math.max(0, Math.min(1, x));
const smooth = (x) => { x = clamp(x); return x * x * x * (x * (x * 6 - 15) + 10); };
const softland = (x) => { x = clamp(x); return 1 - Math.pow(1 - x, 3); };
const accel = (x) => { x = clamp(x); return x * x * x; };
const lerp = (a, b, k) => a + (b - a) * k;
const col = (h) => new T.Color(h);
const tmpC = new T.Color(), tmpO = new T.Object3D(), tmpV = new T.Vector3();

// Keyframed number: [[t, value], ...], eased between neighbours. Duplicated times make a step.
function keyf(arr, t) {
  if (t <= arr[0][0]) return arr[0][1];
  for (let i = 0; i < arr.length - 1; i++) {
    if (t < arr[i + 1][0]) { const a = arr[i], b = arr[i + 1], d = b[0] - a[0]; return d <= 0 ? b[1] : lerp(a[1], b[1], smooth((t - a[0]) / d)); }
  }
  return arr[arr.length - 1][1];
}
function keyc(arr, t, out) {
  if (t <= arr[0][0]) return out.set(arr[0][1]);
  for (let i = 0; i < arr.length - 1; i++) {
    if (t < arr[i + 1][0]) { const a = arr[i], b = arr[i + 1], d = b[0] - a[0]; out.set(a[1]); if (d > 0) out.lerp(tmpC.set(b[1]), smooth((t - a[0]) / d)); else out.set(b[1]); return out; }
  }
  return out.set(arr[arr.length - 1][1]);
}

function rbox(w, h, d, r = 0.1, seg = 3) {
  const g = new T.BoxGeometry(w, h, d, seg * 2, seg * 2, seg * 2), p = g.attributes.position, n = g.attributes.normal;
  const v = new T.Vector3(), q = new T.Vector3(), ix = w / 2 - r, iy = h / 2 - r, iz = d / 2 - r;
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    q.set(Math.max(-ix, Math.min(ix, v.x)), Math.max(-iy, Math.min(iy, v.y)), Math.max(-iz, Math.min(iz, v.z)));
    const dir = v.clone().sub(q);
    if (dir.lengthSq() < 1e-9) continue;
    dir.normalize();
    p.setXYZ(i, q.x + dir.x * r, q.y + dir.y * r, q.z + dir.z * r);
    n.setXYZ(i, dir.x, dir.y, dir.z);
  }
  return g;
}
// A flat slab with a rounded-rectangle outline, for the section floor and plinths. Top face sits at y = h / 2.
function slab(w, d, h, rc, seg = 8) {
  const out = [], pos = [], nor = [], idx = [];
  const corners = [[w / 2 - rc, d / 2 - rc, 0], [-w / 2 + rc, d / 2 - rc, 1], [-w / 2 + rc, -d / 2 + rc, 2], [w / 2 - rc, -d / 2 + rc, 3]];
  corners.forEach(([cx, cz, q]) => { for (let i = 0; i <= seg; i++) { const a = (q + i / seg) * Math.PI / 2; out.push([cx + Math.cos(a) * rc, cz + Math.sin(a) * rc, Math.cos(a), Math.sin(a)]); } });
  const n = out.length, e = Math.min(0.05, h / 3);
  pos.push(0, h / 2, 0); nor.push(0, 1, 0);
  out.forEach(([x, z]) => { pos.push(x, h / 2, z); nor.push(0, 1, 0); });
  for (let i = 0; i < n; i++) idx.push(0, 1 + (i + 1) % n, 1 + i);
  const base = pos.length / 3;
  out.forEach(([x, z, nx, nz]) => { pos.push(x, h / 2, z); nor.push(nx * 0.8, 0.6, nz * 0.8); pos.push(x, -h / 2, z); nor.push(nx, 0, nz); });
  for (let i = 0; i < n; i++) { const a = base + i * 2, b = base + ((i + 1) % n) * 2; idx.push(a, b, a + 1, b, b + 1, a + 1); }
  const g = new T.BufferGeometry();
  g.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); g.setAttribute("normal", new T.Float32BufferAttribute(nor, 3)); g.setIndex(idx);
  return g;
}
// One rounded disc in a lathe profile, walked from the inside up.
function discProfile(pts, rOut, rIn, y0, y1, e) {
  pts.push(new T.Vector2(rIn, y0));
  for (let i = 0; i <= 5; i++) { const a = -Math.PI / 2 + (i / 5) * (Math.PI / 2); pts.push(new T.Vector2(rOut - e + Math.cos(a) * e, y0 + e + Math.sin(a) * e)); }
  for (let i = 0; i <= 5; i++) { const a = (i / 5) * (Math.PI / 2); pts.push(new T.Vector2(rOut - e + Math.cos(a) * e, y1 - e + Math.sin(a) * e)); }
  pts.push(new T.Vector2(rIn, y1));
}
function softSprite(kind, w, h, blur, alpha) {
  const cv = document.createElement("canvas"), S = 256; cv.width = S; cv.height = S;
  const c = cv.getContext("2d"); c.clearRect(0, 0, S, S);
  c.shadowColor = `rgba(74,64,48,${alpha})`; c.shadowBlur = blur; c.shadowOffsetX = S * 3; c.fillStyle = "#000";
  if (kind === "round") { c.beginPath(); c.arc(S / 2 - S * 3, S / 2, S * 0.5 * w, 0, Math.PI * 2); c.fill(); }
  else { const W = S * w, H = S * h; c.beginPath(); c.roundRect(S / 2 - W / 2 - S * 3, S / 2 - H / 2, W, H, 20); c.fill(); }
  const t = new T.Texture(cv); t.needsUpdate = true; t.colorSpace = T.SRGBColorSpace; return t;
}

export function create({ words, base, pages, onReady }) {
  const LW = words.simple;
  const gl = document.createElement("canvas");
  const renderer = new T.WebGLRenderer({ canvas: gl, antialias: true, alpha: false, stencil: false, powerPreference: "high-performance" });
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.NoToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = 3; // soft variance shadows; the build has no exported name for it
  renderer.setClearColor(PAPER, 1);
  let alive = true;
  gl.addEventListener("webglcontextlost", (e) => { e.preventDefault(); alive = false; });

  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(15, 2, 4, 900);
  scene.add(new T.HemisphereLight("#FFFDF8", "#E4DECF", 1.6));
  const sun = new T.DirectionalLight("#FFFEFA", 2.15);
  sun.position.set(-13, 26, 15);
  sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -26, right: 26, top: 26, bottom: -26, near: 2, far: 80 });
  sun.shadow.radius = 5; sun.shadow.blurSamples = 10; sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.02;
  scene.add(sun, sun.target);

  // Floor: paper color only, with a shadow layer on it. It also hides anything below y = 0.
  const floorDepth = new T.Mesh(new T.PlaneGeometry(900, 900), new T.MeshBasicMaterial({ colorWrite: false }));
  floorDepth.rotation.x = -Math.PI / 2; floorDepth.renderOrder = -2; scene.add(floorDepth);
  const floodDisc = new T.Mesh(new T.CircleGeometry(1, 96), new T.MeshBasicMaterial({ color: PAPER, depthTest: false, depthWrite: false }));
  floodDisc.rotation.x = -Math.PI / 2; floodDisc.renderOrder = -3; scene.add(floodDisc);
  const floodRing = new T.Mesh(new T.RingGeometry(0.985, 1, 128), new T.MeshBasicMaterial({ color: BLUE, transparent: true, opacity: 0, depthWrite: false }));
  floodRing.rotation.x = -Math.PI / 2; floodRing.position.y = 0.03; floodRing.renderOrder = 1; scene.add(floodRing);
  const shadowFloor = new T.Mesh(new T.PlaneGeometry(900, 900), new T.ShadowMaterial({ color: "#4A4030", opacity: 0.2, depthWrite: false }));
  shadowFloor.rotation.x = -Math.PI / 2; shadowFloor.position.y = 0.02; shadowFloor.receiveShadow = true; shadowFloor.renderOrder = 0; scene.add(shadowFloor);

  const ceramic = (c, o = {}) => new T.MeshStandardMaterial({ color: c, roughness: 0.62, metalness: 0, ...o });
  const M = {
    plinth: ceramic("#FBF8F0"), plT: ceramic("#FBF8F0"), plO: ceramic("#FBF8F0"), plN: ceramic("#FBF8F0"), sect: ceramic("#FAF7EF", { roughness: 0.8 }), rim: ceramic(INK, { roughness: 0.5 }),
    agentScreen: new T.MeshBasicMaterial({ color: BLUE }), body: ceramic("#FFFDF8", { roughness: 0.42 }),
    bandT: ceramic(QUIET, { emissive: "#000000" }), bandO: ceramic(QUIET, { emissive: "#000000" }),
    core: ceramic(GREY, { roughness: 0.28, emissive: "#000000" }), ring: ceramic(INK, { roughness: 0.4 }),
    acore: ceramic(RUST, { roughness: 0.28, emissive: "#000000" }), aring: ceramic(INK, { roughness: 0.4 }),
    bar: ceramic(READY, { roughness: 0.5 }),
  };
  const setG = new T.Group(); scene.add(setG);

  // Station: a plinth with a database on its back half and a work tray on its front half.
  const PW = 6.3, PD = 7.9, DBZ = -1.65, TRAYZ = 2.15, DBY = 0.3;
  const plinthGeo = slab(PW, PD, 0.3, 0.5);
  const dbPts = []; const dH = 0.62, gap = 0.26;
  [0, 1, 2].forEach((i) => discProfile(dbPts, 2.1, i === 0 ? 0 : 1.72, i * (dH + gap), i * (dH + gap) + dH, 0.13));
  dbPts.push(new T.Vector2(0, 3 * dH + 2 * gap));
  const dbGeo = new T.LatheGeometry(dbPts, 56);
  const bandGeo = new T.CylinderGeometry(1.95, 1.95, 3 * dH + 2 * gap - 0.5, 56, 1, true);
  const DBH = 3 * dH + 2 * gap;
  function station(mat, plMat) {
    const g = new T.Group();
    const p = new T.Mesh(plinthGeo, plMat); p.position.y = 0.15; p.receiveShadow = true; p.castShadow = true; g.add(p);
    const d = new T.Mesh(dbGeo, M.body); d.position.set(0, DBY, DBZ); d.castShadow = true; d.receiveShadow = true; g.add(d);
    const b = new T.Mesh(bandGeo, mat); b.position.set(0, DBY + DBH / 2, DBZ); g.add(b);
    setG.add(g); return g;
  }
  const stT = station(M.bandT, M.plT), stO = station(M.bandO, M.plO);
  // Teleion Fabric: a bounded section that holds the nodes. Agents stand outside it and connect across a bridge.
  let sectMeshes = [], agentG = new T.Group(); setG.add(agentG);
  function buildSection() {
    sectMeshes.forEach((m) => setG.remove(m)); sectMeshes = [];
    while (agentG.children.length) agentG.remove(agentG.children[0]);
    const B = L.sect, w = B.x1 - B.x0, d = B.z1 - B.z0, cx = (B.x0 + B.x1) / 2, cz = (B.z0 + B.z1) / 2;
    const rim = new T.Mesh(slab(w, d, 0.12, 0.9), M.rim); rim.position.set(cx, -0.08, cz); rim.castShadow = true;
    const top = new T.Mesh(slab(w - 0.2, d - 0.2, 0.14, 0.82), M.sect); top.position.set(cx, -0.07, cz); top.receiveShadow = true;
    setG.add(rim, top); sectMeshes.push(rim, top);
    const Ag = L.agent, bridge = new T.Mesh(slab(1.5, Ag.z - 1.1 - B.z1 + 0.3, 0.12, 0.05), M.plinth);
    bridge.position.set(Ag.x, -0.08, (Ag.z - 1.1 + B.z1) / 2); bridge.receiveShadow = true; agentG.add(bridge);
    const pl = new T.Mesh(slab(3.2, 2.4, 0.18, 0.4), M.plinth); pl.position.set(Ag.x, -0.05, Ag.z); pl.receiveShadow = true; pl.castShadow = true; agentG.add(pl);
    const body = new T.Mesh(rbox(1.8, 1.08, 0.3, 0.1, 2), M.body); body.position.set(Ag.x, 0.86, Ag.z - 0.25); body.castShadow = true; agentG.add(body);
    const stem = new T.Mesh(rbox(0.5, 0.42, 0.3, 0.06, 2), M.body); stem.position.set(Ag.x, 0.22, Ag.z - 0.25); stem.castShadow = true; agentG.add(stem);
    const scr = new T.Mesh(new T.PlaneGeometry(1.56, 0.84), M.agentScreen); scr.position.set(Ag.x, 0.86, Ag.z - 0.09); agentG.add(scr);
  }

  // OmniNode: a turned pedestal, a core, and a ring that carries five beads.
  const nPts = [[0, 0.3], [1.5, 0.3], [1.45, 0.42], [1.2, 0.56], [0.9, 0.86], [0.72, 1.12], [0.68, 1.3], [0.82, 1.38], [0.82, 1.44], [0, 1.44]].map(([x, y]) => new T.Vector2(x, y));
  const nodeBodyGeo = new T.LatheGeometry(nPts, 48);
  const nodePlateGeo = new T.CylinderGeometry(2.75, 2.8, 0.3, 64);
  const coreGeo = new T.SphereGeometry(0.72, 40, 28), ringGeo = new T.TorusGeometry(1.34, 0.05, 12, 96), beadGeo = new T.SphereGeometry(0.13, 16, 12);
  function makeNode(coreMat, ringMat, beads, plMat) {
    const g = new T.Group();
    const plate = new T.Mesh(nodePlateGeo, plMat); plate.position.y = 0.15; plate.receiveShadow = true; plate.castShadow = true; g.add(plate);
    const body = new T.Mesh(nodeBodyGeo, M.body); body.castShadow = true; g.add(body);
    const core = new T.Mesh(coreGeo, coreMat); core.position.y = 2.1; core.castShadow = true; g.add(core);
    const ringH = new T.Group(); ringH.position.y = 2.1; ringH.rotation.x = 1.18; g.add(ringH);
    const ring = new T.Group(); ringH.add(ring);
    const r = new T.Mesh(ringGeo, ringMat); r.castShadow = true; ring.add(r);
    let beadsM = null;
    if (beads) {
      beadsM = new T.InstancedMesh(beadGeo, ceramic("#FFFFFF", { roughness: 0.3 }), 5); beadsM.castShadow = false;
      for (let i = 0; i < 5; i++) { const a = (i / 5) * Math.PI * 2; tmpO.position.set(Math.cos(a) * 1.34, Math.sin(a) * 1.34, 0); tmpO.rotation.set(0, 0, 0); tmpO.scale.set(1, 1, 1); tmpO.updateMatrix(); beadsM.setMatrixAt(i, tmpO.matrix); beadsM.setColorAt(i, col(QUIET)); }
      ring.add(beadsM);
    }
    setG.add(g); return { g, core, ring, beadsM };
  }
  const node = makeNode(M.core, M.ring, true, M.plN), audit = makeNode(M.acore, M.aring, false, M.plinth);
  audit.g.scale.setScalar(0.6);

  // Instanced workers of the story.
  const MAXT = 26, MAXC = 16, MAXP = 12;
  const tiles = new T.InstancedMesh(rbox(0.96, 0.24, 0.96, 0.09, 2), ceramic("#FFFFFF", { roughness: 0.5 }), MAXT);
  const cubes = new T.InstancedMesh(rbox(0.82, 0.82, 0.82, 0.11, 2), ceramic("#FFFFFF", { roughness: 0.5 }), MAXC);
  const pegs = new T.InstancedMesh(rbox(0.36, 0.36, 0.36, 0.06, 1), ceramic("#FFFFFF", { roughness: 0.5 }), 9);
  const links = new T.InstancedMesh(rbox(1, 0.13, 0.26, 0.05, 1), ceramic("#FFFFFF", { roughness: 0.5 }), 5);
  const sparks = new T.InstancedMesh(new T.SphereGeometry(0.19, 16, 12), ceramic(BLUE, { roughness: 0.3 }), MAXP);
  [tiles, cubes, pegs, links, sparks].forEach((m) => { m.castShadow = true; m.frustumCulled = false; setColor(m, m.count); setG.add(m); });
  function setColor(m, n) { for (let i = 0; i < n; i++) m.setColorAt(i, col("#FFFFFF")); }
  const bar = new T.Mesh(rbox(6.0, 0.3, 1.1, 0.1, 2), M.bar); bar.castShadow = true; setG.add(bar);

  // Soft contact shadows on the floor, under each base.
  const aoT = softSprite("rect", 0.62, 0.72, 36, 0.62), aoR = softSprite("round", 0.62, 0, 34, 0.62);
  const aoMat = new T.MeshBasicMaterial({ map: aoT, transparent: true, depthWrite: false, opacity: 0.8 }), aoMatR = new T.MeshBasicMaterial({ map: aoR, transparent: true, depthWrite: false, opacity: 0.8 });
  const aoPlane = new T.PlaneGeometry(1, 1);
  const aos = [new T.Mesh(aoPlane, aoMat), new T.Mesh(aoPlane, aoMat), new T.Mesh(aoPlane, aoMatR), new T.Mesh(aoPlane, aoMatR)];
  aos.forEach((m) => { m.rotation.x = -Math.PI / 2; m.position.y = 0.012; m.renderOrder = 1; setG.add(m); });

  // The room of real Eranos pages. Each page scrolls while the camera is on it.
  const roomG = new T.Group(); roomG.visible = false; scene.add(roomG);
  const R_C = new T.Vector3(0, 0, 10), R_R = 34, R_STEP = 28 * Math.PI / 180;
  let screens = [];
  const pageImgs = pages.map((p) => { const img = new Image(); img.src = base + p.src; return img; });
  const frameMat = ceramic("#FFFDF8", { roughness: 0.5 }), standMat = ceramic("#FBF8F0");
  const exampleTex = (() => {
    const cv = document.createElement("canvas"); cv.width = 320; cv.height = 96;
    const c = cv.getContext("2d"); c.fillStyle = RUST; c.beginPath(); c.roundRect(0, 0, 320, 96, 14); c.fill();
    c.fillStyle = CARD; c.font = "700 52px ui-monospace,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(LW.example, 160, 50);
    const t = new T.Texture(cv); t.needsUpdate = true; t.colorSpace = T.SRGBColorSpace; return t;
  })();
  function buildRoom(aspectTall) {
    while (roomG.children.length) roomG.remove(roomG.children[0]);
    const SW = 14, SH = aspectTall ? 12.4 : 7.8;
    screens = pages.map((p, i) => {
      const a = (i - (pages.length - 1) / 2) * R_STEP, x = R_C.x + Math.sin(a) * R_R, z = R_C.z - Math.cos(a) * R_R, y = SH / 2 + 0.56;
      const g = new T.Group(); g.position.set(x, 0, z); g.rotation.y = -a; roomG.add(g);
      const fr = new T.Mesh(rbox(SW + 0.42, SH + 0.42, 0.3, 0.1, 2), frameMat); fr.position.y = y; g.add(fr);
      const st = new T.Mesh(rbox(SW * 0.5, 0.42, 2.4, 0.12, 2), standMat); st.position.y = 0.21; g.add(st);
      const img = pageImgs[i], tex = new T.Texture(img); tex.colorSpace = T.SRGBColorSpace; tex.generateMipmaps = true; tex.minFilter = 1008; tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
      const rep = Math.min(1, (SH / SW) / p.aspect); tex.repeat.set(1, rep); tex.offset.set(0, 1 - rep);
      const up = () => { tex.needsUpdate = true; if (onReady) onReady(); };
      if (img.complete && img.naturalWidth) up(); else img.addEventListener("load", up, { once: true });
      const pl = new T.Mesh(new T.PlaneGeometry(SW, SH), new T.MeshBasicMaterial({ map: tex, toneMapped: false })); pl.position.set(0, y, 0.17); g.add(pl);
      if (p.example) {
        const tag = new T.Mesh(new T.PlaneGeometry(2.5, 0.75), new T.MeshBasicMaterial({ map: exampleTex, transparent: true, toneMapped: false }));
        tag.position.set(SW / 2 - 1.5, y + SH / 2 - 0.65, 0.2); g.add(tag);
      }
      const ao = new T.Mesh(aoPlane, aoMat); ao.rotation.x = -Math.PI / 2; ao.position.set(0, 0.025, 0); ao.scale.set(SW * 0.9, 6, 1); g.add(ao); g.userData.ao = ao;
      return { g, a, tex, rep, SW, SH, y, label: p.label };
    });
  }

  // Layouts: a row on wide frames, a triangle on tall ones.
  const LAY = {
    wide: { tall: false, tasks: { x: -9.2, z: 0 }, node: { x: 0, z: 0.4 }, objs: { x: 9.2, z: 0 }, audit: { x: 4.42, z: -2.75 }, sect: { x0: -13.15, x1: 13.15, z0: -4.75, z1: 5.5 }, agent: { x: 0, z: 8.7 }, elev: 33, labelAt: "below" },
    tall: { tall: true, tasks: { x: -3.65, z: -3.4 }, node: { x: 0, z: 5.5 }, objs: { x: 3.65, z: -3.4 }, audit: { x: 5.0, z: 5.6 }, sect: { x0: -7.3, x1: 7.3, z0: -7.9, z1: 11.3 }, agent: { x: 3.9, z: 13.8 }, elev: 42, labelAt: "above" },
  };
  let L = null, acts = [], view = { W: 0, H: 0, band: 0, D: 40, shift: 0, center: new T.Vector3(), fitted: false };
  const dirOf = (elevDeg, azDeg) => { const e = elevDeg * Math.PI / 180, a = azDeg * Math.PI / 180; return tmpV.set(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e)).clone(); };

  function buildTimeline() {
    acts = [];
    const S = L.tasks, O = L.objs, N = L.node, A = L.audit, Ag = L.agent;
    const tray = (i, j = 0) => [S.x + (i - 2) * 1.16, 0.42, S.z + TRAYZ - 0.45 + j * 1.14];
    const otray = (i) => [O.x + (i - 1.5) * 1.38, 0.72, O.z + TRAYZ];
    const tIn = [S.x, 1.3, S.z + DBZ], oIn = [O.x, 1.3, O.z + DBZ];
    const holdL = [N.x - 1.95, 2.25, N.z + 0.5], holdR = [N.x + 1.95, 2.25, N.z + 0.5], top = [N.x, 3.28, N.z];
    const aTop = [A.x, 2.1, A.z], aIn = [A.x, 0.9, A.z], agentOut = [Ag.x, 1.0, Ag.z - 0.25];
    const pilePos = (i) => [N.x - 2.0 + [0, 0.09, -0.07, 0.05, -0.1, 0.08, 0, 0.04][i % 8], 0.42 + i * 0.25, N.z + 1.05 + [0, -0.08, 0.1, 0.03, -0.05, 0.07, 0, -0.03][i % 8]];
    const R = (i) => [S.x + (i - 2) * 1.24, 0.46, S.z + TRAYZ];
    const a = (kind, keys, o = {}) => { const x = { kind, keys, ...o }; acts.push(x); return x; };
    const K = (t, p, c, o) => ({ t, p, c, ...(o || {}) });
    const run = (keys, t0, from, tDone, tBack, tEnd, cFrom = READY, hold = top) => {
      keys.push(K(t0, from, cFrom), K(t0 + 0.7, hold, cFrom, { arc: 1.4 }), K(tDone, hold, cFrom), K(tDone + 0.2, hold, DONE), K(tBack, hold, DONE), K(tEnd, from, DONE, { arc: 1.4 }));
    };
    const cubeRun = (keys, t0, from, tBack, tEnd, hold = holdR) => {
      keys.push(K(t0, from, OBJ), K(t0 + 0.25, from, OBJ_ON), K(t0 + 0.95, hold, OBJ_ON, { arc: 1.5 }), K(tBack, hold, OBJ_ON), K(tEnd, from, OBJ_ON, { arc: 1.5 }), K(tEnd + 0.4, from, OBJ));
    };
    const stock = (t0, t1, idx, j, c, keysFn) => {
      const keys = [K(t0, tIn, c), K(t0 + 0.55, tray(idx, j), c, { arc: 1.1 })];
      if (keysFn) keysFn(keys, tray(idx, j));
      keys.push(K(t1 - 0.55, keys[keys.length - 1].p, keys[keys.length - 1].c), K(t1, tIn, keys[keys.length - 1].c, { arc: 1.1 }));
      return a("tile", keys);
    };

    // 0:00 Title and hook. An agent outside hands in a Task; the node does work; then one is refused.
    stock(-2, 12.6, 0, 0, READY, (k, p) => { k.push(K(0.8, p, READY)); run(k, 0.8, p, 2.3, 3.0, 4.0); k.push(K(11.9, p, DONE)); });
    stock(-2, 12.6, 2, 0, READY, (k, p) => { k.push(K(4.2, p, READY)); run(k, 4.2, p, 5.7, 6.5, 7.5); k.push(K(11.9, p, DONE)); });
    stock(-2, 12.6, 4, 0, READY, (k, p) => { k.push(K(7.3, p, READY)); run(k, 7.3, p, 8.1, 8.4, 9.2); });
    a("tile", [K(1.6, agentOut, READY), K(2.8, tray(1), READY, { arc: 1.2 }), K(9.1, tray(1), READY),
      K(9.8, top, READY, { arc: 1.3 }), K(9.95, top, LOST), K(10.6, [N.x - 1.35, 0.42, N.z + 1.55], LOST, { arc: 0.5, ry: 0.9 }), K(12.0, [N.x - 1.35, 0.42, N.z + 1.55], LOST, { ry: 0.9 })]);
    const c0 = [K(-2, otray(1), OBJ)]; cubeRun(c0, 1.2, otray(1), 2.2, 3.2);
    c0.push(K(16.01, otray(1), OBJ), K(16.35, otray(1), OBJ_ON), K(24.5, otray(1), OBJ_ON), K(25.2, otray(1), OBJ), K(27.5, otray(1), OBJ), K(28.1, oIn, OBJ, { arc: 1 }));
    a("cube", c0);
    a("cube", [K(-2, otray(2), OBJ), K(27.5, otray(2), OBJ), K(28.1, oIn, OBJ, { arc: 1 })]);

    // 0:14 Tasks pile up.
    for (let i = 0; i < 8; i++) {
      const t = 14.48 + i * 0.17, p = pilePos(i), ry = [0.2, -0.3, 0.45, -0.1, 0.3, -0.4, 0.15, -0.2][i], from = i % 3 === 2 ? agentOut : tIn;
      const keys = [K(t - 0.1, from, READY), K(t + 0.75, p, READY, { arc: 2.0, ry })];
      if (i === 7) keys.push(K(18.61, p, READY, { ry }), K(19.2, [N.x - 2.9, 0.42, N.z + 2.3], LOST, { arc: 0.3, ry: 0.5 }), K(20.8, [N.x - 4.0, 0.2, N.z + 3.3], LOST, { ry: 1.5 }), K(21.9, [N.x - 4.25, -0.5, N.z + 3.6], LOST, { ry: 2.0 }));
      else keys.push(K(24.4 + i * 0.1, p, READY, { ry }), K(25.4 + i * 0.1, tIn, READY, { arc: 2.0 }));
      a("tile", keys);
    }
    // 0:16 It rewrites what exists: a second, identical Object forms at the node.
    const dupSpot = [N.x + 1.75, 0.72, N.z + 1.1];
    a("cube", [K(16.01, [N.x, 2.1, N.z], OBJ_ON), K(16.7, top, OBJ_ON), K(17.4, top, OBJ_ON), K(18.1, dupSpot, OBJ_ON, { arc: 0.4 }), K(24.6, dupSpot, OBJ_ON), K(25.5, otray(1), OBJ_ON, { arc: 2.2 }), K(25.55, oIn, OBJ)]);

    // 0:31 Durable Tasks: small Tasks come out, and the most suited agent picks up one.
    [0, 1, 2, 3, 4].forEach((i) => {
      const t = 33.08 + i * 0.22, p = tray(i), keys = [K(t, tIn, READY), K(t + 0.6, p, READY, { arc: 1.2 })];
      if (i === 1) { keys.push(K(35.7, p, READY)); run(keys, 35.7, p, 37.0, 37.6, 38.6); }
      if (i === 2) keys.push(K(61.57, p, READY), K(62.2, holdL, READY, { arc: 1.2 }), K(63.1, holdL, READY), K(63.3, holdL, PALE), K(63.85, p, DONE, { arc: 1.2 }));
      if (i === 3) keys.push(K(63.87, p, READY), K(64.5, top, READY, { arc: 1.3 }), K(65.6, top, READY), K(65.8, top, DONE), K(66.3, top, DONE), K(67.2, p, DONE, { arc: 1.3 }));
      if (i === 4) keys.push(K(67.6, p, READY), K(68.3, top, READY, { arc: 1.3 }), K(69.2, top, READY), K(69.4, top, DONE), K(69.7, top, DONE), K(70.5, p, DONE, { arc: 1.3 }));
      keys.push(K(70.6, p, keys[keys.length - 1].c), K(71.3 + i * 0.05, tIn, keys[keys.length - 1].c, { arc: 1.1 }));
      a("tile", keys);
    });

    // 0:41 Durable Task Objects, one by one, then stacked versions. They stay on the tray until Eranos.
    const cubeKeys = [0, 1, 2, 3].map((i) => {
      const t = [41.32, 43.14, 45.07, 45.76][i];
      return [K(t, oIn, OBJ_ON), K(t + 0.7, otray(i), OBJ_ON, { arc: 1.4 }), K([43.1, 45.05, 45.75, 47.7][i], otray(i), OBJ_ON), K([43.5, 45.45, 46.15, 48.1][i], otray(i), OBJ)];
    });
    const plate = (n) => [otray(0)[0], otray(0)[1] + 0.41 + 0.15 + 0.27 * n, otray(0)[2]];
    const plates = [0, 1, 2].map((n) => {
      const t = 47.9 + n * 0.72;
      return a("cube", [K(t, [otray(0)[0], 6, otray(0)[2]], OBJ_ON, { sy: 0.32 }), K(t + 0.55, plate(n), OBJ_ON, { sy: 0.32 }), K(51.0, plate(n), OBJ_ON, { sy: 0.32 }), K(51.5, plate(n), OBJ, { sy: 0.32 }), K(180.5, plate(n), OBJ, { sy: 0.32 })]);
    });
    cubeRun(cubeKeys[0], 63.87, otray(0), 65.7, 66.7, holdR);
    cubeRun(cubeKeys[3], 67.6, otray(3), 69.3, 70.3, holdR);
    a("spark", [K(62.4, top, BLUE, { s: 0.2 }), K(62.6, top, BLUE, { s: 1 }), K(63.1, holdL, BLUE, { s: 1 }), K(63.3, holdL, BLUE, { s: 0.1 })]);

    // 1:14 Long work. One long job, too big for the node. It splits into five small Tasks, and they finish one by one.
    const barAt = R(2);
    view.barAct = a("bar", [K(74.16, [S.x, 6.5, barAt[2]], READY), K(74.85, barAt, READY), K(75.1, barAt, READY), K(75.9, [N.x - 2.2, 2.45, N.z + 0.5], READY, { arc: 1.2 }), K(76.3, [N.x - 2.2, 2.45, N.z + 0.5], READY), K(77.1, barAt, READY, { arc: 1.2 }), K(78.09, barAt, READY)]);
    const gk = [0, 1, 2, 3, 4].map((i) => {
      const contig = [S.x + (i - 2) * 1.2, 0.46, barAt[2]];
      return [K(78.09, contig, READY, { sx: 1.25 }), K(78.7, R(i), READY), K(79.0, R(i), i ? WAIT : READY)];
    });
    const picks = [[80.31, 81.9, 82.92, 83.5], [83.7, 84.6, 84.65, 85.2], [85.3, 86.1, 86.15, 86.7], [86.8, 87.5, 87.55, 88.0]];
    picks.forEach(([t0, tD, tB, tE], i) => {
      const k = gk[i];
      k.push(K(t0 - 0.2, R(i), i ? WAIT : READY), K(t0, R(i), READY), K(t0 + 0.5, top, READY, { arc: 1.2 }), K(tD, top, READY), K(tD + 0.1, top, DONE), K(tB, top, DONE), K(tE, R(i), DONE, { arc: 1.2 }));
    });
    { const k = gk[4]; k.push(K(87.85, R(4), WAIT), K(88.05, R(4), READY), K(88.5, top, READY, { arc: 1.2 }), K(88.8, top, READY), K(88.9, top, DONE), K(89.45, aTop, DONE, { arc: 0.35 }), K(90.0, aTop, DONE), K(90.75, R(4), DONE, { arc: 1.4 })); }
    gk.forEach((k, i) => { k.push(K(90.8, R(i), DONE), K(91.45 + i * 0.05, tIn, DONE, { arc: 1.1 })); const x = a("tile", k); x.digit = i + 1; });
    const newPlate = (n, t0, t1) => a("cube", [K(t0, aIn, OBJ_ON, { sy: 0.32 }), K(t0 + 0.2, aTop, OBJ_ON, { sy: 0.32 }), K(t1, plate(n), OBJ_ON, { sy: 0.32, arc: 1.6 }), K(t1 + 1.2, plate(n), OBJ_ON, { sy: 0.32 }), K(t1 + 1.8, plate(n), OBJ, { sy: 0.32 }), K(180.5, plate(n), OBJ, { sy: 0.32 })]);
    newPlate(3, 90.0, 90.85);

    // 1:38 The ways, one at a time.
    const ways = [
      { t0: 98.18, t1: 101.35, tile: 0, cube: 2 }, { t0: 101.35, t1: 104.53, tile: 1, cube: 1 }, { t0: 104.53, t1: 108.22, tile: 2, cube: 0 },
    ];
    const stockKeys = [0, 1, 2, 3, 4].map((i) => { const t = 91.2 + i * 0.1; return [K(t, tIn, READY), K(t + 0.6, tray(i), READY, { arc: 1.1 })]; });
    ways.forEach((w) => {
      const p = tray(w.tile), d = w.t1 - w.t0, k = stockKeys[w.tile], kc = cubeKeys[w.cube], q = otray(w.cube), tDone = w.t0 + d * 0.62;
      k.push(K(w.t0, p, READY), K(w.t0 + Math.min(0.7, d * 0.3), holdL, READY, { arc: 1.2 }), K(tDone - 0.4, holdL, READY), K(tDone, top, READY), K(tDone + 0.15, top, DONE), K(w.t1 - 0.45, top, DONE), K(w.t1 + 0.3, p, DONE, { arc: 1.2 }));
      kc.push(K(w.t0, q, OBJ), K(w.t0 + 0.15, q, OBJ_ON), K(w.t0 + Math.min(0.75, d * 0.34), holdR, OBJ_ON, { arc: 1.3 }), K(w.t1 - 0.5, holdR, OBJ_ON), K(w.t1 + 0.25, q, OBJ_ON, { arc: 1.3 }), K(w.t1 + 0.7, q, OBJ));
    });
    // 1:48 Continuously learning: a recorded run goes through the separate node, returns as a new version, and the next run is quicker.
    { const k = stockKeys[4], p = tray(4); k.push(K(108.5, p, READY), K(109.2, top, READY, { arc: 1.3 }), K(109.6, top, DONE), K(110.2, aTop, DONE, { arc: 0.35 }), K(110.75, aTop, DONE), K(111.5, p, DONE, { arc: 1.4 })); }
    newPlate(4, 110.7, 111.5);
    { const k = stockKeys[3], p = tray(3); k.push(K(111.55, p, READY), K(112.0, top, READY, { arc: 1 }), K(112.2, top, DONE), K(112.85, p, DONE, { arc: 1 })); }
    // 1:55 Knowledge of new projects: a feed maintenance Task sits in Durable Tasks. Its result becomes a Task Object.
    const feedAt = [otray(3)[0], otray(3)[1] + 0.56, otray(3)[2]];
    { const k = stockKeys[3], p = tray(3); k.push(K(114.7, p, DONE), K(114.82, p, READY), K(115.35, top, READY, { arc: 1.2 }), K(115.5, top, DONE), K(116.15, p, DONE, { arc: 1.2 })); }
    a("cube", [K(115.45, [N.x, 2.9, N.z], OBJ_ON, { sy: 0.32 }), K(116.2, feedAt, OBJ_ON, { sy: 0.32, arc: 1.3 }), K(117.4, feedAt, OBJ_ON, { sy: 0.32 }), K(118.0, feedAt, OBJ, { sy: 0.32 }), K(180.5, feedAt, OBJ, { sy: 0.32 })]);
    // More reuse of working code: the same Object is used, with no new one made.
    cubeRun(cubeKeys[0], 116.28, otray(0), 118.9, 119.7, holdR);
    { const k = stockKeys[1], p = tray(1); k.push(K(116.28, p, DONE), K(116.42, p, READY), K(117.1, holdL, READY, { arc: 1.2 }), K(118.1, holdL, READY), K(118.45, top, READY), K(118.6, top, DONE), K(118.9, top, DONE), K(119.7, p, DONE, { arc: 1.2 })); }
    // Long-term tasks that finish: Tasks finish one by one.
    [0, 2, 3, 4, 1].forEach((i, n) => {
      const t = 120.12 + n * 0.32, p = tray(i), lift = [p[0], p[1] + 0.45, p[2]], k = stockKeys[i], last = k[k.length - 1];
      k.push(K(t - 0.02, last.p, READY), K(t + 0.15, lift, READY), K(t + 0.2, lift, DONE), K(t + 0.45, p, DONE));
    });
    const flow = (from, to, period) => {
      let n = 0;
      for (let t = from; t < to - period * 0.8; t += period, n++) {
        const i = [2, 0, 3, 1, 4][n % 5], k = stockKeys[i], p = tray(i), dd = period * 0.4;
        k.push(K(t, p, DONE), K(t + 0.15, p, READY), K(t + dd, top, READY, { arc: 1.2 }), K(t + dd + 0.25, top, READY), K(t + dd + 0.35, top, DONE), K(t + dd + 0.4, top, DONE), K(t + period - 0.05, p, DONE, { arc: 1.2 }));
      }
    };
    flow(122.3, 135, 2.1);
    flow(135.4, 146.3, 1.8);
    stockKeys.forEach((k, i) => { k.push(K(146.3, tray(i), DONE)); a("tile", k); });
    cubeKeys.forEach((k, i) => { k.push(K(146.3, otray(i), OBJ), K(180.5, otray(i), OBJ)); a("cube", k); });
    // 2:55 Connect. The set returns; an agent outside hands in one Task, and the node picks it up.
    [0, 1, 3, 4].forEach((i) => a("tile", [K(176, tray(i), DONE), K(180.5, tray(i), DONE)]));
    a("tile", [K(177.25, agentOut, READY), K(178.0, tray(2), READY, { arc: 1.6 }), K(178.2, tray(2), READY), K(178.8, top, READY, { arc: 1.2 }), K(179.4, top, READY), K(179.55, top, DONE), K(180.5, top, DONE)]);

    // Couplers between Tasks in order: real parts that hold a Task back, and drop when the one before reports back.
    const open = [83.5, 85.2, 86.7, 88.0];
    view.links = [0, 1, 2, 3].map((i) => ({ a: R(i), b: R(i + 1), open: open[i] }));
    view.pegCenter = [N.x, 0.48, N.z + 1.8];
    view.anchors = { S, O, N, A, Ag, top, holdL, holdR, aTop, otray, tray, R };
  }

  // Time-keyed state of the set.
  const FLOODS = [[12, TONE], [28, PAPER], [71, CARD], [91, PAPER], [113, TONE], [135, PAPER], [146.75, CARD], [176.3, PAPER]];
  // The three parts light one at a time, in the owner's order, then all together.
  const lit = {
    t: [[0, 0], [31.5, 0], [31.85, 1], [38.7, 1], [38.94, 0], [67.3, 0], [67.6, 1]],
    o: [[0, 0], [39.3, 0], [39.65, 1], [50.0, 1], [50.3, 0], [67.3, 0], [67.6, 1]],
    n: [[0, 0], [50.85, 0], [51.2, 1]],
  };
  const tint = [[0, 1], [68.6, 1], [71, 0.0]];
  // The one being talked about gets large; the others step back. After "Together", all three are even.
  const focusT = [[0, 0], [31.5, 0], [31.85, 1], [38.7, 1], [38.94, 0]], focusO = [[0, 0], [39.3, 0], [39.65, 1], [50.0, 1], [50.3, 0]], focusN = [[0, 0], [50.85, 0], [51.2, 1], [67.3, 1], [67.6, 0]];
  const dimOf = (t, f) => (t > 31.3 && t < 67.45 ? 1 - clamp(keyf(f, t)) : 0);
  const coreColor = [[0, GREY], [7.25, GREY], [7.5, BLUE], [9.6, BLUE], [9.95, RUST], [11.6, RUST], [12.0, GREY], [50.85, GREY], [51.2, BLUE], [98.18, BLUE], [98.45, INK], [101.1, INK], [101.4, BLUE], [104.5, BLUE], [104.8, PALE], [108.0, PALE], [108.3, BLUE]];
  const coreSize = [[0, 1], [22.25, 1], [23.8, 1.85], [24.4, 1.85], [25.5, 1], [126.79, 1], [128.2, 0.66], [146, 0.66], [176, 0.66], [176.1, 1]];
  const coreGlow = [[0, 0], [7.25, 0], [7.5, 0.5], [8.6, 0.12], [53.89, 0.12], [54.2, 0.55], [55.3, 0.18], [101.35, 0.18], [101.75, 0.55], [104.3, 0.25]];
  const beadOn = [55.55, 56.73, 57.36, 58.17, 59.45];
  const SPIN = [[0.8, 3.2, 1.2], [4.2, 6.5, 1.2], [7.25, 8.4, 1.8], [22.25, 24.4, 2.4], [35.9, 37.6, 1.6], [53.89, 61, 1.1], [63.9, 66.3, 1.4], [67.6, 69.7, 1.6], [80.6, 82.9, 2], [83.7, 88.9, 2], [94.64, 97.9, 1.5], [101.35, 104.53, 3], [108.3, 113, 2.0], [122.3, 146.3, 0.9]];
  const ringAngle = (t) => {
    let a = t * 0.42;
    for (const [f, to, k] of SPIN) a += k * (Math.max(f, Math.min(to, t)) - f);
    if (t > 98.18) { const p = Math.min(2.75, t - 98.18) / 0.55, s = Math.floor(p); a += (s + smooth((p - s) / 0.5)) * (Math.PI / 4) - Math.min(2.75, t - 98.18) * 0.42; }
    return a;
  };
  
  const auditUp = (t) => keyf([[87.1, -3.4], [87.9, 0]], t);
  const sinkOf = (t) => keyf([[146.4, 0], [148.0, -7], [175.9, -7], [177.0, 0]], t);

  // Camera beats on the set: gentle pan and push, so each scene has its own framing.
  const SHOT = (x, z, zoom) => ({ x, z, zoom });
  function shotAt(t) {
    const wide = !L.tall, S = L.tasks, N = L.node, O = L.objs;
    const rows = [
      [0, 0, 0, 1.0], [12, 0, 0, 1.0], [28, 0, 0, 1.0],
      [71, wide ? S.x * 0.56 : 0, wide ? -2.6 : -0.5, wide ? 0.68 : 0.94], [87.1, 0, 0, 1.0], [113, 0, 0, 1.0], [135, 0, 0, 1.0], [176.0, 0, 0, 1.0],
    ];
    let x = 0, z = 0, zoom = 1;
    const gl = 1.2;
    for (let i = 0; i < rows.length; i++) {
      const [tt, rx, rz, rzm] = rows[i], k = i === 0 ? 1 : smooth((t - tt) / gl);
      x = lerp(x, rx, k); z = lerp(z, rz, k); zoom = lerp(zoom, rzm, k);
    }
    return { x, z, zoom };
  }

  // Camera beats in the Eranos room: angle and how far away, as multiples of one screen.
  const ROOMS = [[147.2, 1.5, 1.75], [153.5, 0, 1], [155.06, 1, 1], [157.65, 2, 1], [160.44, 3, 1], [163.84, 4, 1], [166.64, 5, 1], [169.66, 2.5, 1.75]];
  function roomCam(t) {
    let idx = ROOMS[0][1], far = ROOMS[0][2];
    for (let i = 1; i < ROOMS.length; i++) { const k = smooth((t - ROOMS[i][0]) / (i === 1 ? 1.2 : 0.85)); idx = lerp(idx, ROOMS[i][1], k); far = lerp(far, ROOMS[i][2], k); }
    return { idx, far };
  }
  const SCROLL = [[149, 155.1], [154.8, 157.7], [157.3, 160.5], [160.2, 163.9], [163.6, 166.7], [166.3, 175]];

  function fit(W, H) {
    const tall = W / H < 1.05, newL = tall ? LAY.tall : LAY.wide;
    if (L !== newL) {
      L = newL; buildTimeline(); buildRoom(tall);
      buildSection(); stT.position.set(L.tasks.x, 0, L.tasks.z); stO.position.set(L.objs.x, 0, L.objs.z);
      node.g.position.set(L.node.x, 0, L.node.z); audit.g.position.set(L.audit.x, 0, L.audit.z);
      const P = [L.tasks, L.objs, L.node, L.audit], Sz = [[PW * 1.5, PD * 1.45], [PW * 1.5, PD * 1.45], [8.6, 8.6], [4.8, 4.8]];
      aos.forEach((m, i) => { m.position.x = P[i].x; m.position.z = P[i].z; m.scale.set(Sz[i][0], Sz[i][1], 1); });
    }
    const band = H * (tall ? 0.3 : 0.215), botPad = tall ? 74 : 62, sidePad = tall ? 12 : 44;
    camera.aspect = W / H; camera.clearViewOffset(); camera.updateProjectionMatrix();
    const pts = [];
    const B = L.sect;
    for (const x of [B.x0, B.x1]) for (const z of [B.z0, B.z1]) for (const y of [0, 0.1]) pts.push(new T.Vector3(x, y, z));
    [L.tasks, L.objs].forEach((s) => pts.push(new T.Vector3(s.x, DBY + DBH + (tall ? 1.7 : 0.3), s.z + DBZ)));
    pts.push(new T.Vector3(L.node.x, 4.3, L.node.z), new T.Vector3(L.agent.x - 1.6, 0, L.agent.z + 1.2), new T.Vector3(L.agent.x + 1.6, 0, L.agent.z + 1.2));
    const mid = new T.Vector3((B.x0 + B.x1) / 2, 1.0, (B.z0 + L.agent.z) / 2);
    const dir = dirOf(L.elev, 0);
    const measure = (D) => {
      camera.position.copy(mid).addScaledVector(dir, D); camera.lookAt(mid); camera.updateMatrixWorld();
      let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
      for (const p of pts) { const q = p.clone().project(camera); const sx = (q.x + 1) / 2 * W, sy = (1 - q.y) / 2 * H; x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy); }
      return { x0, x1, y0, y1 };
    };
    const safeW = W - sidePad * 2, safeH = H - band - botPad;
    let lo = 8, hi = 500;
    for (let i = 0; i < 26; i++) { const m = (lo + hi) / 2, b = measure(m); if (b.x1 - b.x0 <= safeW && b.y1 - b.y0 <= safeH) hi = m; else lo = m; }
    const b = measure(hi);
    view.W = W; view.H = H; view.band = band; view.D = hi; view.mid = mid; view.shift = (band + (H - botPad)) / 2 - (b.y0 + b.y1) / 2;
    view.botPad = botPad; view.fitted = true;
    // Eranos room: a screen fills the safe area.
    const s0 = screens[0], px = (2 * Math.tan(7.5 * Math.PI / 180));
    const roomSafeW = W - (tall ? 20 : 80), roomSafeH = H - band - (tall ? 56 : 62);
    const dW = (s0.SW + 0.5) * (H / roomSafeW) / px, dH = (s0.SH + 0.5) * (H / roomSafeH) / px;
    view.roomD = Math.max(dW, dH);
    view.roomShift = (band + (H - (tall ? 56 : 62))) / 2 - H / 2;
  }

  const proj = new T.Vector3();
  const project = (p) => { proj.set(p[0], p[1], p[2]).project(camera); return [(proj.x + 1) / 2 * view.W, (1 - proj.y) / 2 * view.H]; };

  function evalKeys(act, t, out) {
    const keys = act.keys, n = keys.length;
    if (t < keys[0].t || t > keys[n - 1].t) return false;
    let i = 0;
    while (i < n - 2 && t >= keys[i + 1].t) i++;
    const a = keys[i], b = keys[i + 1] || a, d = b.t - a.t, k = d > 0 ? smooth((t - a.t) / d) : 1;
    out.x = lerp(a.p[0], b.p[0], k); out.y = lerp(a.p[1], b.p[1], k); out.z = lerp(a.p[2], b.p[2], k);
    if (b.arc) out.y += Math.sin(k * Math.PI) * b.arc;
    out.ry = lerp(a.ry || 0, b.ry || 0, k);
    out.s = lerp(a.s === undefined ? 1 : a.s, b.s === undefined ? 1 : b.s, k);
    out.sy = lerp(a.sy === undefined ? 1 : a.sy, b.sy === undefined ? 1 : b.sy, k);
    out.sx = lerp(a.sx === undefined ? 1 : a.sx, b.sx === undefined ? 1 : b.sx, k);
    out.c = out.c || new T.Color(); out.c.set(a.c || "#FFFFFF"); if (b.c && d > 0) out.c.lerp(tmpC.set(b.c), k); else if (b.c && k >= 1) out.c.set(b.c);
    return true;
  }
  const pos = { c: new T.Color() };
  const cubeAtForLabel = {};

  function update(t) {
    // Actors.
    let nT = 0, nC = 0, nS = 0; bar.visible = false;
    for (const a of acts) {
      if (!evalKeys(a, t, pos)) continue;
      if (a.kind === "bar") {
        bar.visible = true; bar.position.set(pos.x, pos.y, pos.z); M.bar.color.copy(pos.c); continue;
      }
      tmpO.position.set(pos.x, pos.y, pos.z); tmpO.rotation.set(0, pos.ry, 0);
      tmpO.scale.set(pos.s * pos.sx, pos.s * pos.sy, pos.s); tmpO.updateMatrix();
      if (a.kind === "tile" && nT < MAXT) { tiles.setMatrixAt(nT, tmpO.matrix); tiles.setColorAt(nT++, pos.c); }
      else if (a.kind === "cube" && nC < MAXC) { cubes.setMatrixAt(nC, tmpO.matrix); cubes.setColorAt(nC++, pos.c); }
      else if (a.kind === "spark" && nS < MAXP) { sparks.setMatrixAt(nS, tmpO.matrix); sparks.setColorAt(nS++, pos.c); }
    }
    tiles.count = nT; cubes.count = nC; sparks.count = nS;
    tiles.visible = nT > 0; cubes.visible = nC > 0; sparks.visible = nS > 0;
    tiles.instanceMatrix.needsUpdate = true; if (tiles.instanceColor) tiles.instanceColor.needsUpdate = true;
    cubes.instanceMatrix.needsUpdate = true; if (cubes.instanceColor) cubes.instanceColor.needsUpdate = true;
    sparks.instanceMatrix.needsUpdate = true; if (sparks.instanceColor) sparks.instanceColor.needsUpdate = true;

    // Couplers: hold a Task back, then drop away when the Task before it reports back.
    const showL = t > 79 && t < 91.2;
    links.visible = showL;
    if (showL) {
      view.links.forEach((l, i) => {
        const dx = l.b[0] - l.a[0], dz = l.b[2] - l.a[2], len = Math.hypot(dx, dz);
        const up = smooth((t - 79) / 0.5), drop = smooth((t - l.open) / 0.35), out = smooth((t - 90.8) / 0.4);
        tmpO.position.set((l.a[0] + l.b[0]) / 2, 0.3 + 0.24 * up - 0.42 * Math.max(drop * 0.6, out), (l.a[2] + l.b[2]) / 2);
        tmpO.rotation.set(0, -Math.atan2(dz, dx), 0); tmpO.scale.set(Math.max(0.1, len - 0.5), 1.3, 1.4); tmpO.updateMatrix();
        links.setMatrixAt(i, tmpO.matrix);
        links.setColorAt(i, tmpC.set(drop > 0.5 ? BLUE : RUST));
      });
      links.count = 4; links.instanceMatrix.needsUpdate = true; if (links.instanceColor) links.instanceColor.needsUpdate = true;
    }
    // Search grid.
    const showP = t > 94.6 && t < 98.4;
    pegs.visible = showP;
    if (showP) {
      const best = 5, up = smooth((t - 94.64) / 0.6) * (1 - smooth((t - 97.6) / 0.6)), sweep = (t - 96.02) / 0.09;
      for (let i = 0; i < 9; i++) {
        const gx = (i % 3 - 1) * 0.52, gz = (Math.floor(i / 3) - 1) * 0.52, c = view.pegCenter;
        const isBest = i === best && t > 96.81, on = t > 96.02 && Math.floor(sweep) % 9 === i && t < 96.81;
        tmpO.position.set(c[0] + gx, 0.14 + up * (0.35 + (isBest ? 0.3 * smooth((t - 96.81) / 0.3) : 0)), c[2] + gz);
        tmpO.rotation.set(0, 0, 0); tmpO.scale.set(1, 1, 1); tmpO.updateMatrix(); pegs.setMatrixAt(i, tmpO.matrix);
        pegs.setColorAt(i, tmpC.set(isBest ? BLUE : on ? READY : WAIT));
      }
      pegs.instanceMatrix.needsUpdate = true; if (pegs.instanceColor) pegs.instanceColor.needsUpdate = true;
    }

    // Lighting of the three parts.
    const lT = keyf(lit.t, t), lO = keyf(lit.o, t), lN = keyf(lit.n, t);
    M.bandT.color.set(QUIET).lerp(tmpC.set(BLUE), lT);
    M.bandO.color.set(QUIET).lerp(tmpC.set(RUST), lO);
    M.plT.color.set("#FBF8F0").lerp(tmpC.set("#CFDCF0"), lT * keyf(tint, t));
    M.plO.color.set("#FBF8F0").lerp(tmpC.set("#EBCDBD"), lO * keyf(tint, t));
    M.plN.color.set("#FBF8F0").lerp(tmpC.set("#CFDCF0"), lN * keyf(tint, t));
    M.rim.color.set(INK).lerp(tmpC.set(BLUE), keyf([[0, 0], [28.24, 0], [28.6, 1]], t));
    keyc(coreColor, t, M.core.color);
    const cg = keyf(coreGlow, t);
    M.core.emissive.copy(M.core.color); M.core.emissiveIntensity = cg;
    const size = keyf(coreSize, t);
    node.core.scale.setScalar(size);
    node.ring.rotation.z = ringAngle(t);
    // Beads light one by one with the voice, then stay.
    for (let i = 0; i < 5; i++) { const on = t > beadOn[i] ? (t < 146.5 ? 1 : 0) : 0; node.beadsM.setColorAt(i, tmpC.set(on ? BLUE : QUIET)); }
    node.beadsM.instanceColor.needsUpdate = true;
    node.ring.children[0].material.color.set(lN > 0.5 ? BLUE : INK);

    const aUp = auditUp(t);
    audit.g.position.y = aUp; audit.g.visible = t > 86.5;
    audit.ring.rotation.z = t * 0.7 + (t > 89 ? Math.min(1, t - 89) * 3 : 0) + Math.max(0, Math.min(t, 113) - 111.5) * 3;
    const aGlow = Math.max(smooth((t - 89.3) / 0.3) * (1 - smooth((t - 90.3) / 0.4)), smooth((t - 111.8) / 0.3) * (1 - smooth((t - 112.8) / 0.4)));
    M.acore.emissive.set(RUST); M.acore.emissiveIntensity = 0.1 + aGlow * 0.7;

    // Stage: the set folds down into the floor for Eranos, and returns for Connect.
    const sink = sinkOf(t);
    setG.position.y = 0.14 + sink; setG.visible = sink > -6.9;
    aos.forEach((m, i) => { m.visible = i < 3 || t > 87.3; });

    const room = t > 146.35 && t < 177.4;
    roomG.visible = room;
    if (room) {
      const up = keyf([[146.4, -13], [147.7, 0], [175.9, 0], [176.8, -13.5]], t);
      const rc = roomCam(t);
      screens.forEach((s, i) => {
        const lag = Math.abs(i - 1.6) * 0.12, u = t < 150 ? keyf([[146.4 + lag, -14], [147.6 + lag, 0]], t) : up;
        s.g.position.y = u;
        s.g.visible = u > -13; s.g.userData.ao.visible = t > 148.2;
        const [f, to] = SCROLL[i], k = smooth((t - f) / (to - f));
        s.tex.offset.y = (1 - s.rep) * (1 - k);
      });
    }
    // Flood the ground from the node at each scene change.
    let base2 = PAPER, cur = null, curT = 0, ringAlpha = 0;
    for (const [ft, fc] of FLOODS) { if (t >= ft + 0.95) base2 = fc; else if (t >= ft) { cur = fc; curT = ft; } }
    renderer.setClearColor(base2, 1);
    floodDisc.visible = !!cur; floodRing.visible = !!cur;
    if (cur) {
      const k = (t - curT) / 0.95, r = 2.8 + accel(k * 0.8 + 0.2) * 160;
      floodDisc.material.color.set(cur); floodDisc.scale.set(r, r, 1);
      floodDisc.position.set(L.node.x, 0, L.node.z); floodRing.position.set(L.node.x, 0.03, L.node.z); floodRing.scale.set(r, r, 1);
      floodRing.material.opacity = 0.7 * (1 - clamp(k * 1.4));
    }

    // Camera.
    const sh = shotAt(t), sway = Math.sin(t * 0.13) * 1.1, breath = Math.sin(t * 0.09) * 0.25;
    const setD = view.D * sh.zoom, dir = dirOf(L.elev + breath, sway);
    const camPos = new T.Vector3().copy(view.mid); camPos.x += sh.x; camPos.z += sh.z;
    const setLook = camPos.clone(); camPos.addScaledVector(dir, setD);
    const toRoom = keyf([[146.5, 0], [148.1, 1], [175.9, 1], [177.1, 0]], t);
    let shift = view.shift;
    if (toRoom > 0) {
      const rc = roomCam(t), a = (rc.idx - (pages.length - 1) / 2) * R_STEP, SH = screens[0].SH, cy = SH / 2 + 0.56;
      const tp = new T.Vector3(R_C.x + Math.sin(a) * R_R, cy, R_C.z - Math.cos(a) * R_R);
      const out = new T.Vector3(-Math.sin(a), 0, Math.cos(a)), dist = view.roomD * rc.far;
      const rp = tp.clone().addScaledVector(out, dist); rp.y += Math.sin(t * 0.2) * 0.05;
      rp.x += Math.sin(t * 0.17) * 0.12;
      camPos.lerp(rp, toRoom); setLook.lerp(tp, toRoom);
      shift = lerp(view.shift, view.roomShift, toRoom);
    }
    camera.position.copy(camPos); camera.lookAt(setLook);
    camera.setViewOffset(view.W, view.H, 0, -shift, view.W, view.H);
    camera.updateMatrixWorld();
  }

  // Everything that needs a word on it, as screen-space records for film.js to draw.
  const P3 = { c: new T.Color() };
  function labels(t) {
    const out = [], A = view.anchors, sink = sinkOf(t), up = (p) => [p[0], p[1] + sink + 0.14, p[2]], fade = 1 + sink * 0.8;
    if (sink > -1.2) {
      const below = L.labelAt === "below", front = PD / 2 + 0.1;
      const part = (S, text, on, foc, color) => {
        const p = below ? project(up([S.x, 0, S.z + front])) : project(up([S.x, DBY + DBH + 0.1, S.z + DBZ - 0.4]));
        out.push({ kind: "label", x: p[0], y: p[1], text, on, focus: keyf(foc, t), dim: dimOf(t, foc), color, place: below ? "below" : "above", alpha: fade });
      };
      part(A.S, LW.tasks, keyf(lit.t, t), focusT, BLUE);
      part(A.O, LW.objects, keyf(lit.o, t), focusO, RUST);
      const np = project(up([A.N.x, 0, A.N.z + (L.tall ? 2.45 : 2.82)]));
      out.push({ kind: "label", x: np[0], y: np[1], text: LW.node, on: keyf(lit.n, t), focus: keyf(focusN, t), dim: dimOf(t, focusN), place: "below", sub: t > 53.46 ? LW.intel : LW.node_sub, alpha: fade });
      // Teleion Fabric names the bounded section; agents stand outside it.
      const B = L.sect, sp = project(up([B.x0 + 0.5, 0, B.z1 + 0.1]));
      out.push({ kind: "label", x: sp[0], y: sp[1], text: LW.section, left: true, on: keyf([[28.24, 0], [28.5, 1], [31.0, 1], [31.3, 0]], t), focus: keyf([[28.24, 0], [28.5, 1], [31.0, 1], [31.3, 0]], t), place: "below", alpha: fade });
      const ag = project(up([A.Ag.x, 0, A.Ag.z + 1.25]));
      out.push({ kind: "label", x: ag[0], y: ag[1], text: LW.agent, on: 0, small: 1, place: "below", alpha: fade, dim: dimOf(t, [[0, 0]]) * 0.6 });
      if (t > 87.4 && t < 135) {
        const ap = project(up([A.A.x, L.tall ? 2.5 : 2.75, A.A.z]));
        out.push({ kind: "label", x: ap[0], y: ap[1], text: LW.audit, on: 0, small: 1, place: "above", alpha: clamp((t - 87.4) / 0.4) });
      }
      // Numbers on the small Tasks, so "one by one" can be read.
      if (t > 78.5 && t < 90.9) acts.forEach((a) => {
        if (!a.digit || !evalKeys(a, t, pos)) return;
        const q = project(up([pos.x, pos.y + 0.14, pos.z]));
        out.push({ kind: "digit", x: q[0], y: q[1], text: String(a.digit), done: pos.c.b > 0.45 && pos.c.r < 0.2, alpha: clamp((t - 78.5) / 0.3) });
      });
      for (const pl of PILLS) {
        if (t < pl.from || t >= pl.to) continue;
        let w;
        if (L.tall && ["objs", "stack", "plate", "tasks"].includes(pl.at)) w = [pl.at === "tasks" ? A.S.x : A.O.x, 0.2, A.O.z + PD / 2 + 2.5];
        else if (pl.at === "top") w = [A.N.x, L.tall ? 3.45 : 3.95, A.N.z];
        else if (pl.at === "right") w = [A.holdR[0], A.holdR[1] + 0.55, A.holdR[2]];
        else if (pl.at === "objs") w = [A.O.x, DBY + DBH + 1.0, A.O.z + DBZ - 0.6];
        else if (pl.at === "stack") w = [A.otray(0)[0], 2.2, A.otray(0)[2]];
        else if (pl.at === "plate") w = [A.otray(3)[0], 1.6, A.otray(3)[2]];
        else if (pl.at === "tasks") w = [A.S.x, DBY + DBH + 1.0, A.S.z + DBZ - 0.6];
        else if (pl.at === "bar") { if (!evalKeys(view.barAct, t, pos)) continue; w = [pos.x, pos.y + 0.3, pos.z]; }
        else w = pl.at;
        const q = project(up(w));
        out.push({ kind: "pill", x: q[0], y: q[1], text: pl.text, sub: pl.sub, accent: pl.c, alpha: clamp((t - pl.from) / 0.2) * clamp((pl.to - t) / 0.14) });
      }
    }
    if (t > 148.2 && t < 175.6) {
      const rc = roomCam(t), near = Math.round(rc.idx);
      if (rc.far < 1.3 && Math.abs(rc.idx - near) < 0.15) {
        const s = screens[near], a = s.a, cx = R_C.x + Math.sin(a) * R_R, cz = R_C.z - Math.cos(a) * R_R;
        const q = project([cx, s.y - s.SH / 2 - 0.2, cz]);
        out.push({ kind: "label", x: q[0], y: q[1], text: s.label, on: 0, place: "below", small: 1, alpha: 1 - Math.abs(rc.idx - near) / 0.15 });
      }
    }
    return out;
  }
  const W_ = LW.ways;
  const PILLS = [
    { from: 41.32, to: 43.1, at: "objs", text: LW.objs_list[0], c: RUST }, { from: 43.14, to: 45.03, at: "objs", text: LW.objs_list[1], c: RUST },
    { from: 45.07, to: 45.72, at: "objs", text: LW.objs_list[2], c: RUST }, { from: 45.76, to: 47.68, at: "objs", text: LW.objs_list[3], c: RUST },
    { from: 48.0, to: 48.68, at: "stack", text: LW.versions[0], c: RUST }, { from: 48.7, to: 49.4, at: "stack", text: LW.versions[1], c: RUST }, { from: 49.42, to: 50.25, at: "stack", text: LW.versions[2], c: RUST },
    { from: 53.89, to: 55.5, at: "top", text: LW.meta, c: BLUE },
    ...[0, 1, 2, 3, 4].map((i) => ({ from: beadOn[i], to: i < 4 ? beadOn[i + 1] - 0.04 : 61.4, at: "top", text: LW.intel_list[i], c: BLUE })),
    { from: 74.4, to: 78.05, at: "bar", text: LW.long_job, c: BLUE },
    { from: 98.18, to: 101.3, at: "top", text: W_[0], c: BLUE }, { from: 99.0, to: 101.05, at: "right", text: LW.way_objects[0], c: RUST },
    { from: 101.35, to: 104.48, at: "top", text: W_[1], sub: LW.meta, c: BLUE }, { from: 102.2, to: 104.25, at: "right", text: LW.way_objects[1], c: RUST },
    { from: 104.53, to: 108.16, at: "top", text: W_[2], c: BLUE }, { from: 105.4, to: 107.9, at: "right", text: LW.way_objects[2], c: RUST },
    { from: 108.22, to: 112.85, at: "top", text: W_[3], sub: LW.recorded, c: BLUE },
    { from: 114.7, to: 115.7, at: "tasks", text: LW.feed_task, c: BLUE }, { from: 115.7, to: 116.24, at: "plate", text: LW.feed_result, c: RUST },
    { from: 117.1, to: 118.9, at: "right", text: LW.objs_list[0], c: RUST },
  ];

  function draw(t, W, H, pr) {
    if (!alive) return null;
    if (W !== view.W || H !== view.H || !view.fitted) {
      renderer.setPixelRatio(pr); renderer.setSize(W, H, false); fit(W, H);
    } else if (renderer.getPixelRatio() !== pr) { renderer.setPixelRatio(pr); renderer.setSize(W, H, false); }
    update(t);
    renderer.render(scene, camera);
    return gl;
  }
  return { draw, labels, canvas: gl, get calls() { return renderer.info.render.calls; }, get alive() { return alive; }, view, get layout() { return L; } };
}
