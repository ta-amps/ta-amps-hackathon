// The home film's 3D world: one place, with the camera flying between its stations. It draws no sentence of its own:
// sentences come from the page's article and short labels from content/home.json (film-words.world), so the word gate
// reads them all. Loaded late by film.js on the home page only; if anything fails, film.js keeps its 2D drawings.
// Facts drawn here are sourced in content/home.json. Muse Glimmer 30B and OmniNode stay separate islands on purpose:
// the records don't establish that live workers route through Glimmer or that they run as OmniNodes.
import * as T from "./three-0.187.0.min.js";

const PAPER = "#F5F2EA", CARD = "#FFFDF8", INK = "#11161F", BLUE = "#24519B", RUST = "#A23E1C", SOFT = "#2F343A";
const WORLD_KINDS = new Set(["parts", "file", "omninode", "queue", "workers", "reuse", "eranos"]);
const clamp = (x) => Math.max(0, Math.min(1, x));
const smooth = (x) => { x = clamp(x); return x * x * x * (x * (x * 6 - 15) + 10); };
const lerp = (a, b, k) => a + (b - a) * k;
const V = (x, y, z) => new T.Vector3(x, y, z);

// Stations: where each thing stands. Agents and applications on the left, the shared work in the middle, what's kept on
// the right, and the model path along the back.
const AT = {
  agent: V(-24, 0, -2), eranos: V(-33, 0, 4), gate: V(-15, 0, 5),
  queue: V(-3, 0, 5), spark: V(-7, 0, 1), wonder: V(-1.5, 0, 1), checker: V(5, 0, 1),
  store: V(14, 0, 2), feeds: V(23, 0, 6), shim: V(-10, 0, -10), model: V(2, 0, -10),
  glimmer: V(18, 0, -13), records: V(13.5, 0, -9.5), omni: V(3, 0, 24), tuning: V(9, 0, 12.5),
};
const OMNI_R = 6;
const bayAt = (i) => { const a = -Math.PI / 2 - 0.2 + (i / 5) * Math.PI * 2; return V(AT.omni.x + Math.cos(a) * OMNI_R * 1.25, 0, AT.omni.z + Math.sin(a) * OMNI_R * 0.9); };

// A box with properly rounded edges: the ceramic look needs highlights to roll across corners.
function rbox(w, h, d, r = 0.12, seg = 3) {
  const g = new T.BoxGeometry(w, h, d, seg * 2, seg * 2, seg * 2), p = g.attributes.position, n = g.attributes.normal;
  const v = new T.Vector3(), inner = new T.Vector3(w / 2 - r, h / 2 - r, d / 2 - r), q = new T.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    q.set(Math.max(-inner.x, Math.min(inner.x, v.x)), Math.max(-inner.y, Math.min(inner.y, v.y)), Math.max(-inner.z, Math.min(inner.z, v.z)));
    const dir = v.clone().sub(q);
    if (dir.lengthSq() < 1e-9) continue;
    dir.normalize();
    p.setXYZ(i, q.x + dir.x * r, q.y + dir.y * r, q.z + dir.z * r);
    n.setXYZ(i, dir.x, dir.y, dir.z);
  }
  return g;
}

export const isWorld = (kind) => WORLD_KINDS.has(kind);

export function create({ target, scenes, words, api }) {
  const L = words.world.labels;
  const gl = document.createElement("canvas");
  const small = Math.min(screen.width, screen.height) < 700 || target.clientWidth < 700;
  const renderer = new T.WebGLRenderer({ canvas: gl, antialias: true, powerPreference: "high-performance", alpha: false, stencil: false });
  renderer.setClearColor(PAPER, 1);
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.NoToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFShadowMap;
  let alive = true;
  gl.addEventListener("webglcontextlost", (e) => { e.preventDefault(); alive = false; });

  const scene = new T.Scene();
  scene.fog = new T.Fog(PAPER, 60, 200);
  const camera = new T.PerspectiveCamera(34, 16 / 9, 0.5, 400);

  // Reflections for the glaze: a soft room with bright panels, baked once.
  (() => {
    const env = new T.Scene(), panel = (x, y, z, sx, sy, sz, k) => {
      const m = new T.Mesh(new T.BoxGeometry(sx, sy, sz), new T.MeshBasicMaterial({ color: new T.Color(k, k, k * 0.97) }));
      m.position.set(x, y, z); env.add(m);
    };
    env.add(new T.Mesh(new T.BoxGeometry(40, 30, 40), new T.MeshBasicMaterial({ color: "#C9C4B6", side: T.BackSide })));
    panel(0, 14, 0, 26, 0.5, 14, 5); panel(-19, 6, 4, 0.5, 8, 18, 3.2); panel(18, 4, -8, 0.5, 6, 10, 2); panel(0, 5, 19, 22, 5, 0.5, 2.4);
    const pm = new T.PMREMGenerator(renderer);
    scene.environment = pm.fromScene(env, 0.035).texture;
    scene.environmentIntensity = 0.5;
    pm.dispose();
  })();
  const glaze = (color, o = {}) => new T.MeshStandardMaterial({ color, roughness: 0.22, metalness: 0, ...o });
  const M = {
    white: glaze("#FBF8F0"), warm: glaze("#E9E3D5", { roughness: 0.35 }), blue: glaze(BLUE), pale: glaze("#C9D7EE"), rust: glaze(RUST),
    soft: glaze("#3C434D", { roughness: 0.3 }), gold: glaze("#C9A15A", { roughness: 0.25, metalness: 0.5 }), glow: new T.MeshBasicMaterial({ color: BLUE }),
    glowRust: new T.MeshBasicMaterial({ color: RUST }), off: glaze("#D8D1C1", { roughness: 0.6 }), screen: new T.MeshBasicMaterial({ color: "#FFFDF8" }),
    pane: new T.MeshStandardMaterial({ color: "#9DB6DF", roughness: 0.1, transparent: true, opacity: 0.28, side: T.DoubleSide, depthWrite: false }),
  };

  const sky = new T.HemisphereLight("#FFFFFF", "#D8D1C1", 1.0);
  const sun = new T.DirectionalLight("#FFF4E2", 1.5);
  const sunDir = V(-0.42, 1, 0.5).normalize();
  sun.castShadow = true;
  sun.shadow.mapSize.set(small ? 1024 : 2048, small ? 1024 : 2048);
  sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03; sun.shadow.radius = 4;
  sun.shadow.camera.near = 1; sun.shadow.camera.far = 200;
  scene.add(sky, sun, sun.target);

  const add = (geo, mat, x = 0, y = 0, z = 0, o = {}) => {
    const m = new T.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = o.cast !== false; m.receiveShadow = o.receive !== false;
    if (o.rx) m.rotation.x = o.rx; if (o.ry) m.rotation.y = o.ry; if (o.rz) m.rotation.z = o.rz;
    (o.to || scene).add(m);
    return m;
  };
  const slab = (x, z, w, d, h = 0.3) => add(rbox(w, h, d, 0.12), M.white, x, h / 2, z);

  // The ground stays exactly the page's paper; it only catches shadows, and a fine grid fades into the haze.
  const floor = new T.Mesh(new T.PlaneGeometry(500, 500), new T.ShadowMaterial({ color: "#3B3224", opacity: 0.28 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
  (() => {
    const pts = [], R = 80;
    for (let i = -R; i <= R; i += 4) pts.push(i, 0.01, -R, i, 0.01, R, -R, 0.01, i, R, 0.01, i);
    const g = new T.BufferGeometry(); g.setAttribute("position", new T.Float32BufferAttribute(pts, 3));
    scene.add(new T.LineSegments(g, new T.LineBasicMaterial({ color: "#E6E0D2" })));
  })();

  // ---- Paths: glowing routes, each with a bright core and a soft halo. Beads with trails run along them.
  const paths = {};
  function path(id, pts, { col = BLUE, r = 0.09 } = {}) {
    const curve = new T.CatmullRomCurve3(pts.map((p) => V(...p)));
    const len = curve.getLength();
    const core = new T.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.5 });
    const halo = new T.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.1, depthWrite: false });
    const seg = Math.max(16, Math.floor(len * 3));
    const a = new T.Mesh(new T.TubeGeometry(curve, seg, r, 6), core), b = new T.Mesh(new T.TubeGeometry(curve, seg, r * 3, 8), halo);
    scene.add(a, b);
    paths[id] = { curve, len, core, halo, col: new T.Color(col), a: 0 };
  }
  path("agent_gate", [[-22, 0.42, -0.6], [-20, 0.42, 2.2], [-17.6, 0.42, 4.2], [-16.4, 0.7, 4.9]]);
  path("eranos_gate", [[-30.4, 0.42, 4.6], [-26, 0.42, 6.3], [-20, 0.42, 6.2], [-16.4, 0.7, 5.5]]);
  path("agent_shim", [[-22, 0.42, -3.4], [-18, 0.42, -7.6], [-14, 1.1, -9.8], [-10, 2.5, -10]]);
  path("shim_model", [[-10, 2.5, -10], [-6, 2.2, -10], [-2, 1.9, -10], [0.5, 1.8, -10]], { r: 0.13 });
  path("store_shim", [[11.6, 0.42, -0.8], [7, 0.42, -4.4], [0, 0.42, -6], [-6, 1, -7.2], [-10, 2.5, -10]], { r: 0.08 });
  path("wonder_check", [[-1.5, 0.42, 3.05], [1.5, 0.42, 3.2], [4.6, 0.42, 3.05]]);
  path("check_store", [[6.4, 0.42, 2.6], [9, 0.42, 3], [11.6, 0.42, 2.9]]);
  path("feeds_store", [[21.8, 0.42, 5.7], [19.6, 0.42, 4.9], [17.6, 0.42, 3.8]]);
  path("records_glimmer", [[14.6, 0.42, -10], [16, 0.42, -11.6], [17.1, 0.5, -12.4]], { r: 0.08 });
  // Auto-tuning: recorded outcomes come in, and the hourly policy goes back to the workers.
  path("outcomes_tuner", [[13.4, 0.42, 6.2], [12.2, 0.42, 9], [10.6, 0.42, 11.4]]);
  path("tuner_workers", [[7.6, 2.6, 11.6], [4, 4.6, 8], [0.4, 5.4, 4], [-1.5, 4.3, 1.2]], { col: RUST });
  for (let i = 0; i < 5; i++) {
    const b = bayAt(i), a = V(AT.omni.x, 0.5, AT.omni.z);
    path(`omni${i}`, [[a.x, 0.5, a.z], [lerp(a.x, b.x, 0.5), 0.5, lerp(a.z, b.z, 0.5)], [b.x, 0.5, b.z]], { r: 0.08 });
  }

  const BEADS = 260, beadGeo = new T.IcosahedronGeometry(1, 1);
  const beads = new T.InstancedMesh(beadGeo, new T.MeshBasicMaterial({ color: "#FFFFFF" }), BEADS);
  beads.frustumCulled = false; scene.add(beads);
  const dummy = new T.Object3D(), tmpC = new T.Color();
  beads.setColorAt(0, tmpC.set(BLUE));

  // ---- Instanced small things: rollers, Tasks waiting on the belt, version slabs, cards.
  const inst = (geo, mat, n) => { const m = new T.InstancedMesh(geo, mat, n); m.castShadow = true; m.receiveShadow = true; m.frustumCulled = false; scene.add(m); return m; };
  const place = (m, i, x, y, z, s = 1, sy = s, rx = 0, ry = 0) => { dummy.position.set(x, y, z); dummy.scale.set(s, sy, s); dummy.rotation.set(rx, ry, 0); dummy.updateMatrix(); m.setMatrixAt(i, dummy.matrix); };

  // Your agent: a workstation with a live screen.
  slab(AT.agent.x, AT.agent.z, 6, 5);
  const screenBars = [];
  add(rbox(3.6, 0.3, 2, 0.1), M.white, AT.agent.x, 0.6, AT.agent.z + 0.5);
  add(rbox(0.5, 1, 0.4, 0.1), M.white, AT.agent.x, 1.1, AT.agent.z - 0.5);
  const scr = add(rbox(3.9, 2.4, 0.22, 0.1), M.white, AT.agent.x, 2.6, AT.agent.z - 0.3, { rx: -0.12 });
  add(new T.BoxGeometry(3.5, 2, 0.02), M.screen, 0, 0, 0.12, { to: scr, cast: false });
  for (let i = 0; i < 5; i++) screenBars.push(add(new T.BoxGeometry(1, 0.13, 0.02), i % 3 === 2 ? M.glowRust : M.glow, -1.4, 0.7 - i * 0.34, 0.14, { to: scr, cast: false }));

  // Teleion Fabric's door: an arch the queue comes out of.
  slab(AT.gate.x, AT.gate.z, 6.4, 7.5);
  for (const dz of [-2.6, 2.6]) add(rbox(1.5, 5.6, 1.5, 0.22), M.white, AT.gate.x, 3.1, AT.gate.z + dz);
  add(rbox(2.2, 1.4, 7.2, 0.26), M.blue, AT.gate.x, 6.3, AT.gate.z);
  add(rbox(0.4, 0.14, 4, 0.06), M.glow, AT.gate.x - 1.06, 5.5, AT.gate.z, { cast: false });

  // The shared queue: a real belt on rollers.
  slab(-3, 3.2, 21, 7.6);
  const beltL = 19, belt0 = -12.5;
  add(rbox(beltL, 0.34, 2.2, 0.14), M.pale, belt0 + beltL / 2, 0.72, AT.queue.z);
  for (const dz of [-1.25, 1.25]) add(rbox(beltL, 0.5, 0.2, 0.08), M.white, belt0 + beltL / 2, 0.76, AT.queue.z + dz);
  const rollers = inst(new T.CylinderGeometry(0.16, 0.16, 2.5, 8), M.warm, 30);
  for (let i = 0; i < 30; i++) place(rollers, i, belt0 + 0.3 + i * (beltL / 30), 0.46, AT.queue.z, 1, 1, Math.PI / 2);
  rollers.instanceMatrix.needsUpdate = true;
  const BELT_Y = 1.45;
  const waiting = inst(rbox(1.05, 0.9, 1.05, 0.16), M.blue, 7);
  const taskGeo = rbox(1.15, 1, 1.15, 0.17);
  const hero = add(taskGeo, M.blue, belt0, BELT_Y, AT.queue.z);
  const heroTag = add(rbox(0.62, 0.05, 0.62, 0.02), M.white, 0, 0.52, 0, { to: hero, cast: false });

  // Workers: one body design, three check-in arcs at the foot that go out one by one when a worker stops.
  const podPoints = [[0, 0], [1.2, 0], [1.34, 0.14], [1.34, 0.5], [1.26, 1.3], [1.12, 2.1], [0.9, 2.7], [0.55, 3.1], [0, 3.22]].map((p) => new T.Vector2(p[0], p[1]));
  const podGeo = new T.LatheGeometry(podPoints, 28);
  const arcGeo = new T.TorusGeometry(1.72, 0.1, 8, 24, (Math.PI * 2) / 3 - 0.14);
  function pod(pos, band) {
    add(rbox(4.2, 0.22, 3.6, 0.1), M.warm, pos.x, 0.42, pos.z);
    const y0 = 0.5;
    add(podGeo, M.white, pos.x, y0, pos.z);
    add(new T.CylinderGeometry(1.33, 1.33, 0.32, 28), band, pos.x, y0 + 0.92, pos.z);
    add(rbox(1.24, 0.44, 0.3, 0.12), M.soft, pos.x, y0 + 2.08, pos.z + 1.02, { rx: -0.22, cast: false });
    const lamp = add(new T.SphereGeometry(0.2, 12, 10), M.glow, pos.x, y0 + 3.3, pos.z, { cast: false });
    const arcs = [0, 1, 2].map((i) => {
      const mat = new T.MeshBasicMaterial({ color: BLUE });
      return add(arcGeo, mat, pos.x, y0 + 0.08, pos.z, { rx: Math.PI / 2, rz: (i * Math.PI * 2) / 3 + 0.07, cast: false });
    });
    const ripple = add(new T.RingGeometry(1.0, 1.08, 40), new T.MeshBasicMaterial({ color: BLUE, transparent: true, opacity: 0, side: T.DoubleSide, depthWrite: false }), pos.x, y0 + 3.3, pos.z, { rx: Math.PI / 2, cast: false });
    const arm = add(rbox(0.26, 0.26, 1, 0.1), M.white, pos.x, 2.3, pos.z + 1.6);
    return { pos, lamp, arcs, ripple, arm, y0, band };
  }
  const Wa = pod(AT.spark, M.blue), Wb = pod(AT.wonder, M.pale), Wc = pod(AT.checker, M.rust);
  Wc.arm.visible = false;
  const key = new T.Group(); key.position.set(AT.checker.x + 2.2, 3.1, AT.checker.z + 0.8); scene.add(key);
  add(new T.TorusGeometry(0.42, 0.13, 10, 22), M.gold, 0, 0.7, 0, { to: key });
  add(rbox(0.2, 1.1, 0.14, 0.05), M.gold, 0, -0.1, 0, { to: key });
  add(rbox(0.36, 0.14, 0.14, 0.04), M.gold, 0.22, -0.5, 0, { to: key });
  add(rbox(0.28, 0.14, 0.14, 0.04), M.gold, 0.18, -0.25, 0, { to: key });

  // Durable Task Objects: towers of kept versions. The top of each is the latest, the rest stay.
  slab(AT.store.x, AT.store.z, 9.6, 8);
  const TOWERS = [[-2.8, -2, 7], [0, -2.2, 10], [2.8, -2, 5], [-2.8, 1, 4], [0, 1, 8], [2.8, 1, 6]];
  const towerTotal = TOWERS.reduce((a, b) => a + b[2], 0) + TOWERS.length;
  const versionGeo = rbox(2, 0.34, 2, 0.1, 2);
  const versionsOld = inst(versionGeo, M.white, towerTotal), versionsTop = inst(versionGeo, M.blue, TOWERS.length);

  // Feeds: a dish listening for what's new.
  slab(AT.feeds.x, AT.feeds.z, 5, 5);
  add(new T.CylinderGeometry(0.16, 0.26, 3, 12), M.white, AT.feeds.x, 1.8, AT.feeds.z);
  const dishPts = []; for (let i = 0; i <= 10; i++) { const r = i / 10; dishPts.push(new T.Vector2(r * 1.9, r * r * 0.9)); }
  const dish = add(new T.LatheGeometry(dishPts, 24), glazeDouble(), AT.feeds.x, 3.2, AT.feeds.z, { rx: 0.72, rz: 0.3 });
  add(new T.SphereGeometry(0.2, 10, 8), M.glow, 0, 1.5, 0, { to: dish, cast: false });
  add(new T.CylinderGeometry(0.05, 0.05, 1.5, 6), M.soft, 0, 0.75, 0, { to: dish, cast: false });
  add(new T.TorusGeometry(1.9, 0.07, 8, 40), M.white, 0, 0.9, 0, { to: dish, rx: Math.PI / 2 });
  function glazeDouble() { return glaze("#C9D7EE", { side: T.DoubleSide }); }

  // The shim: a frame standing across the model path. It touches every call, and only adds context.
  slab(AT.shim.x, AT.shim.z, 5, 6.6);
  for (const dz of [-2.4, 2.4]) add(rbox(0.8, 5.2, 0.8, 0.16), M.blue, AT.shim.x, 2.9, AT.shim.z + dz);
  for (const y of [0.55, 5.3]) add(rbox(0.8, 0.8, 5.6, 0.16), M.blue, AT.shim.x, y, AT.shim.z);
  add(new T.PlaneGeometry(4.2, 4.2), M.pane, AT.shim.x, 2.9, AT.shim.z, { ry: Math.PI / 2, cast: false, receive: false });
  const contextCards = inst(rbox(0.72, 0.1, 0.5, 0.04, 2), M.white, 16);

  // The agent's model: whichever model it already uses.
  slab(AT.model.x, AT.model.z, 5.4, 5.4);
  add(new T.CylinderGeometry(1.6, 1.9, 0.7, 28), M.warm, AT.model.x, 0.65, AT.model.z);
  const brain = add(new T.SphereGeometry(1.72, 32, 22), M.white, AT.model.x, 2.65, AT.model.z);

  // Muse Glimmer 30B: 52 layers, drawn as 52 rings. Fed only by recorded work; no route to the live workers.
  slab(AT.glimmer.x, AT.glimmer.z, 6.6, 6.6);
  add(new T.CylinderGeometry(2.3, 2.6, 0.5, 32), M.warm, AT.glimmer.x, 0.55, AT.glimmer.z);
  const LAYERS = 52, layerH = 0.145;
  const layers = inst(new T.CylinderGeometry(1, 1, 0.1, 28), M.blue, LAYERS);
  layers.setColorAt(0, tmpC.set(BLUE));
  slab(AT.records.x, AT.records.z, 3, 2.6);
  const recs = inst(rbox(1.7, 0.12, 1.2, 0.04, 2), M.white, 6);
  for (let i = 0; i < 6; i++) place(recs, i, AT.records.x, 0.42 + i * 0.15, AT.records.z, 1, 1, 0, (i % 2) * 0.1);
  recs.instanceMatrix.needsUpdate = true;

  // Eranos: the first application, a house with its two real doors.
  slab(AT.eranos.x, AT.eranos.z, 6.8, 5.6);
  add(rbox(5.4, 3.4, 3.6, 0.22), M.white, AT.eranos.x, 2, AT.eranos.z);
  add(rbox(6, 0.46, 4.2, 0.16), M.warm, AT.eranos.x, 3.9, AT.eranos.z);
  add(rbox(1.5, 2.3, 0.14, 0.1), M.blue, AT.eranos.x - 1.3, 1.5, AT.eranos.z + 1.8);
  add(rbox(1.5, 2.3, 0.14, 0.1), M.rust, AT.eranos.x + 1.3, 1.5, AT.eranos.z + 1.8);

  // OmniNode: one body in the middle, its settings orbiting, and five ways of running on spokes.
  add(new T.CylinderGeometry(9.2, 9.4, 0.3, 44), M.white, AT.omni.x, 0.15, AT.omni.z).scale.set(1.15, 1, 0.92);
  add(podGeo, M.white, AT.omni.x, 0.3, AT.omni.z).scale.set(1.3, 1.2, 1.3);
  add(new T.CylinderGeometry(1.73, 1.73, 0.42, 28), M.blue, AT.omni.x, 1.5, AT.omni.z);
  const settings = inst(rbox(0.8, 0.14, 0.8, 0.05, 2), M.pale, 5);
  const bay = (i) => { const p = bayAt(i); add(new T.CylinderGeometry(1.5, 1.6, 0.3, 24), M.warm, p.x, 0.45, p.z); return p; };
  { const p = bay(0); add(rbox(1.5, 0.5, 1.1, 0.08), M.white, p.x, 0.85, p.z); add(rbox(0.26, 1.2, 0.26, 0.05), M.soft, p.x - 0.3, 1.5, p.z); add(rbox(0.26, 0.8, 0.26, 0.05), M.soft, p.x + 0.3, 1.3, p.z); }
  { const p = bay(1); add(new T.SphereGeometry(0.95, 24, 16), M.blue, p.x, 1.55, p.z); }
  { const p = bay(2); add(new T.SphereGeometry(0.7, 20, 14), M.blue, p.x, 2.2, p.z); add(rbox(1.5, 0.9, 1.5, 0.12), M.white, p.x, 1.05, p.z); add(rbox(0.9, 0.08, 0.9, 0.03), M.rust, p.x, 1.53, p.z, { cast: false }); }
  { const p = bay(3); for (let k = 0; k < 4; k++) add(rbox(1.5, 0.26, 1.5, 0.07, 2), k === 3 ? M.blue : M.white, p.x, 0.75 + k * 0.3, p.z); }
  const loopPos = bay(4);
  add(new T.TorusGeometry(0.85, 0.12, 10, 32), M.rust, loopPos.x, 1.6, loopPos.z, { rx: 0.25 });
  const loopBead = add(new T.SphereGeometry(0.2, 12, 10), M.glowRust, 0, 0, 0, { cast: false });

  // Auto-tuning: a dial that comes round once an hour.
  slab(AT.tuning.x, AT.tuning.z, 5.6, 4.8);
  add(new T.CylinderGeometry(1.5, 1.8, 0.5, 28), M.warm, AT.tuning.x, 0.55, AT.tuning.z);
  const dial = new T.Group(); dial.position.set(AT.tuning.x, 2.7, AT.tuning.z); dial.rotation.x = -0.22; scene.add(dial);
  add(new T.CylinderGeometry(1.9, 1.9, 0.3, 40), M.white, 0, 0, 0, { to: dial, rx: Math.PI / 2 });
  add(new T.TorusGeometry(1.9, 0.09, 8, 48), M.blue, 0, 0, 0.13, { to: dial });
  for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; add(new T.BoxGeometry(0.07, i % 3 ? 0.18 : 0.34, 0.02), M.glow, Math.sin(a) * 1.58, Math.cos(a) * 1.58, 0.16, { to: dial, rz: -a, cast: false }); }
  const dialHand = add(new T.BoxGeometry(0.1, 1.35, 0.03), M.glowRust, 0, 0, 0.19, { to: dial, cast: false });
  add(new T.SphereGeometry(0.15, 12, 10), M.glowRust, 0, 0, 0.19, { to: dial, cast: false });

  // The soft spot of light under whatever the caption is about.
  const spot = add(new T.RingGeometry(0.975, 1, 96), new T.MeshBasicMaterial({ color: BLUE, transparent: true, opacity: 0.8, side: T.DoubleSide, depthWrite: false }), 0, 0.34, 0, { rx: -Math.PI / 2, cast: false, receive: false });
  const spotFill = add(new T.CircleGeometry(0.975, 64), new T.MeshBasicMaterial({ color: "#BFD0EC", transparent: true, opacity: 0.12, depthWrite: false }), 0, 0.33, 0, { rx: -Math.PI / 2, cast: false, receive: false });

  // ---- What the camera does. Each shot looks at a station from a set angle; between shots the camera flies.
  const FOCUS = {
    agent: { at: V(-24, 2, -2), r: 4, d: 21, az: -8, el: 20, paths: ["agent_gate", "agent_shim"] },
    http: { at: V(-20, 2, 1.5), r: 6.5, d: 27, az: -6, el: 28, paths: ["agent_gate"] },
    gate: { at: V(-14, 3.2, 5), r: 5, d: 25, az: 10, el: 20, paths: ["agent_gate", "eranos_gate"] },
    queue: { at: V(-3, 1.8, 4), r: 11, e: 0.5, d: 31, az: -4, el: 25, paths: [] },
    spark: { at: V(-7, 2.6, 3), r: 3.4, d: 18, az: -6, el: 18, paths: [] },
    wonder: { at: V(-1.5, 2.6, 3), r: 3.4, d: 18, az: 8, el: 18, paths: ["wonder_check"] },
    checker: { at: V(5, 2.6, 2), r: 3.6, d: 18, az: 10, el: 18, paths: ["wonder_check", "check_store"] },
    workers: { at: V(-1, 2.4, 2.5), r: 8.5, e: 0.5, d: 25, az: 4, el: 20, paths: ["wonder_check"] },
    wide_agents: { at: V(-13, 1.6, 2), r: 3.2, d: 38, az: 2, el: 28, paths: ["agent_gate"] },
    store: { at: V(14, 2.6, 1.5), r: 6.2, d: 23, az: 10, el: 27, paths: ["check_store", "feeds_store", "store_shim"] },
    feeds: { at: V(21.5, 3, 5.5), r: 3.4, d: 20, az: 8, el: 18, paths: ["feeds_store"] },
    shim: { at: V(-9, 3, -10), r: 4.4, d: 23, az: -12, el: 28, paths: ["agent_shim", "shim_model", "store_shim"] },
    reuse: { at: V(1, 1.4, -6.5), r: 4, d: 36, az: 4, el: 52, paths: ["store_shim", "shim_model", "agent_shim"] },
    model: { at: V(2, 2.6, -10), r: 3.6, d: 20, az: 8, el: 24, paths: ["shim_model"] },
    glimmer: { at: V(17.4, 4.6, -12.5), r: 4.6, d: 25, az: 168, el: 13, paths: ["records_glimmer"] },
    eranos: { at: V(-32.5, 2.3, 4.6), r: 4.6, d: 20, az: 12, el: 16, paths: ["eranos_gate"] },
    omni: { at: V(3, 2, 24), r: 8.8, e: 0.85, d: 30, az: -6, el: 30, paths: ["omni0", "omni1", "omni2", "omni3", "omni4"] },
    tuning: { at: V(8, 2.2, 11), r: 3.8, d: 21, az: 10, el: 24, paths: ["outcomes_tuner", "tuner_workers"] },
    overview: { at: V(-5, 0, 7), r: 0, d: 74, az: -3, el: 46, paths: ["agent_gate", "eranos_gate", "store_shim", "shim_model", "check_store", "feeds_store"] },
  };
  for (let i = 0; i < 5; i++) { const p = bayAt(i); FOCUS[`bay${i}`] = { at: V(p.x, 1.4, p.z), r: 2.4, d: 19, az: (p.x - AT.omni.x) * 1.6, el: p.z < AT.omni.z ? 40 : 24, paths: [`omni${i}`] }; }

  // Timing comes from the page: each scene's length and its steps, so editing the article moves the film with it.
  const sceneNamed = (kind) => scenes.find((s) => s.kind === kind) || { secs: 1, steps: [] };
  const paced = (s, start) => (s.secs - start - 0.6) / Math.max(1, s.steps.length);
  const stepName = (st) => st.map((r) => r.t).join("").trim().split(":")[0];
  const STATION_OF = [[/feed/i, "feeds"], [/task objects/i, "store"], [/shim/i, "shim"], [/durable tasks/i, "queue"], [/custom|glimmer/i, "glimmer"], [/tuning/i, "tuning"]];
  const stationOf = (st) => (STATION_OF.find(([re]) => re.test(stepName(st))) || [null, "overview"])[1];
  const partsScene = sceneNamed("parts"), omniScene = sceneNamed("omninode");
  const omniStart = 3.6, omniEach = paced(omniScene, omniStart), partsStart = 2, partsEach = paced(partsScene, partsStart);
  const partsStations = partsScene.steps.map(stationOf);
  const partsAt = (station) => { const i = partsStations.indexOf(station); return i < 0 ? -1 : partsStart + i * partsEach; };
  const SHOTS = {
    parts: [[0, "overview", null], ...partsStations.map((f, i) => [partsStart + i * partsEach, f, f === "overview" ? null : f])],
    file: [[0, "http", "http"], [2.2, "gate", "gate"], [5.8, "http", "http"]],
    omninode: [[0, "omni", "omni"], ...omniScene.steps.slice(0, 5).map((_, i) => [omniStart + i * omniEach, `bay${i}`, `bay${i}`])],
    queue: [[0, "queue", "queue"], [1.4, "spark", "spark"], [6.6, "wonder", "wonder"], [9.2, "checker", "checker"], [12.2, "store", "store"]],
    workers: [[0, "wide_agents", "agent"], [2, "workers", "wonder"]],
    reuse: [[0, "feeds", "feeds"], [2.6, "store", "store"], [5, "reuse", "reuse"]],
    eranos: [[0, "overview", null], [3, "eranos", "eranos"]],
  };
  const keys = [];
  scenes.forEach((s) => { (SHOTS[s.kind] || []).forEach(([at, f, hi]) => keys.push({ t: s.start + at, f: FOCUS[f], hi, name: f })); });
  const eyeOf = (f) => { const a = (f.az * Math.PI) / 180, e = (f.el * Math.PI) / 180; return V(f.at.x + Math.sin(a) * Math.cos(e) * f.d, f.at.y + Math.sin(e) * f.d, f.at.z + Math.cos(a) * Math.cos(e) * f.d); };
  keys.forEach((k) => { k.eye = eyeOf(k.f); });
  const FLY_LEAD = 0.8, FLY_MAX = 2.6;
  function camState(t) {
    let i = 0;
    while (i < keys.length - 1 && t >= keys[i + 1].t - FLY_LEAD) i++;
    const cur = keys[i], prev = keys[Math.max(0, i - 1)];
    const k = i === 0 ? 1 : smooth((t - (cur.t - FLY_LEAD)) / FLY_MAX);
    return { cur, prev, k };
  }
  const eye = V(0, 0, 0), look = V(0, 0, 0);
  let aspect = 16 / 9;
  function moveCamera(t) {
    const { cur, prev, k } = camState(t);
    eye.lerpVectors(prev.eye, cur.eye, k);
    look.lerpVectors(prev.f.at, cur.f.at, k);
    const hop = prev.eye.distanceTo(cur.eye);
    eye.y += Math.sin(k * Math.PI) * Math.min(hop * 0.2, 8);
    // A slow drift, so the world always has depth, even on a hold.
    const drift = Math.sin(t * 0.21) * 0.07, dx = eye.x - look.x, dz = eye.z - look.z, cs = Math.cos(drift), sn = Math.sin(drift);
    eye.x = look.x + dx * cs - dz * sn; eye.z = look.z + dx * sn + dz * cs;
    // Narrow screens step back, to keep the whole thing in frame.
    const fit = Math.max(1, Math.pow(1.5 / aspect, 0.9));
    eye.sub(look).multiplyScalar(fit).add(look);
    camera.position.copy(eye); camera.lookAt(look);
    const d = eye.distanceTo(look);
    scene.fog.near = d * 1.18; scene.fog.far = d * 2.9;
    // Keep the shadow map on what the camera sees.
    const S = Math.max(16, Math.min(70, d * 1.05)), cam = sun.shadow.camera;
    if (Math.abs(cam.right - S) > 0.5) { cam.left = -S; cam.right = S; cam.top = S; cam.bottom = -S; cam.updateProjectionMatrix(); }
    const tex = (S * 2) / sun.shadow.mapSize.x;
    sun.target.position.set(Math.round(look.x / tex) * tex, 0, Math.round(look.z / tex) * tex);
    sun.position.copy(sun.target.position).addScaledVector(sunDir, 80);
    sun.target.updateMatrixWorld();
    return { cur, prev, k, d };
  }

  // The Task's story, as a pure function of time, so seeking and the two scenes agree. Same marks as the captions.
  function taskStory(s) {
    const belt = (x) => [x, BELT_Y, AT.queue.z], forkA = [AT.spark.x, 2.45, AT.spark.z + 2.1], forkB = [AT.wonder.x, 2.45, AT.wonder.z + 2.1];
    const lerpTo = (a, b, k) => { k = smooth(k); return [lerp(a[0], b[0], k), lerp(a[1], b[1], k) + Math.sin(k * Math.PI) * 0.5, lerp(a[2], b[2], k)]; };
    const at = {
      missed: s < 4.2 ? 0 : s < 4.7 ? 0 : s < 5.2 ? 1 : s < 5.7 ? 2 : 3,
      claimA: s >= 1.4 && s < 5.8, stoppedA: s >= 4.2 && s < 11, claimB: s >= 7.6 && s < 9.3, checking: s >= 10.4 && s < 12.2, kept: s >= 13.6,
    };
    if (s < 1.4) at.pos = belt(lerp(belt0 + 0.5, AT.spark.x, smooth(s / 1.4)));
    else if (s < 2.2) at.pos = lerpTo(belt(AT.spark.x), forkA, (s - 1.4) / 0.8);
    else if (s < 5.8) at.pos = forkA;
    else if (s < 6.6) at.pos = lerpTo(forkA, belt(AT.spark.x), (s - 5.8) / 0.8);
    else if (s < 7.6) at.pos = belt(lerp(AT.spark.x, AT.wonder.x, smooth((s - 6.6) / 1)));
    else if (s < 8.2) at.pos = lerpTo(belt(AT.wonder.x), forkB, (s - 7.6) / 0.6);
    else if (s < 9.2) at.pos = forkB;
    else if (s < 10.4) { const q = paths.wonder_check.curve.getPointAt(smooth((s - 9.2) / 1.2)); at.pos = [q.x, 0.95, q.z]; }
    else if (s < 12.2) { const q = paths.wonder_check.curve.getPointAt(1); at.pos = [q.x, 0.95, q.z]; }
    else if (s < 13.6) { const q = paths.check_store.curve.getPointAt(smooth((s - 12.2) / 1.4)); at.pos = [q.x, 0.95, q.z]; }
    else at.pos = null;
    at.isObject = s >= 9.2;
    at.bad = s >= 4.2 && s < 6.6;
    return at;
  }
  // Which moment of the Task's story to show: the queue scene plays it straight; Durable Tasks plays it fast; elsewhere it loops gently.
  function storyTime(s, st, t) {
    if (s && s.kind === "queue") return st;
    const durable = partsAt("queue");
    if (s && s.kind === "parts" && durable >= 0 && st >= durable && st < durable + partsEach) return (st - durable) * (11.5 / partsEach);
    return ((t * 0.8) % 16);
  }

  const heroPos = V(0, 0, 0);
  let beadN = 0;
  function trail(p, u, n, col, size, gap = 0.012, dir = 1) {
    for (let i = 0; i < n && beadN < BEADS; i++) {
      const q = u - (dir * i * gap) / (p.len / 20);
      const w = ((q % 1) + 1) % 1;
      if ((dir > 0 && q < 0) || (dir < 0 && q > 1)) continue;
      const pt = p.curve.getPointAt(w), s = size * (1 - (i / n) * 0.82);
      dummy.position.copy(pt); dummy.scale.setScalar(s); dummy.rotation.set(0, 0, 0); dummy.updateMatrix();
      beads.setMatrixAt(beadN, dummy.matrix); beads.setColorAt(beadN, tmpC.copy(col)); beadN++;
    }
  }
  const CRUST = new T.Color(RUST), CBLUE = new T.Color(BLUE), CPAPER = new T.Color("#9DB6DF");

  function update(t, s, st, shot) {
    const hi = shot.cur.hi, focusPaths = new Set(shot.cur.f.paths);
    for (const [id, p] of Object.entries(paths)) {
      const a = focusPaths.has(id) ? 1 : 0.28;
      p.core.opacity = lerp(0.2, 0.92, a); p.halo.opacity = lerp(0.03, 0.2, a);
      p.a = a;
    }
    // Beads.
    beadN = 0;
    const flows = [["agent_gate", 0.28, 3], ["eranos_gate", 0.24, 3], ["agent_shim", 0.32, 3], ["store_shim", 0.16, 4], ["feeds_store", 0.3, 2], ["records_glimmer", 0.3, 2], ["check_store", 0.3, 2], ["outcomes_tuner", 0.3, 2], ["tuner_workers", 0.2, 2], ["omni0", 0.4, 1], ["omni1", 0.4, 1], ["omni2", 0.4, 1], ["omni3", 0.4, 1], ["omni4", 0.4, 1]];
    for (const [id, speed, n] of flows) {
      const p = paths[id];
      if (p.a < 0.5 && !(hi === null)) { if (shot.d < 30) continue; }
      for (let i = 0; i < n; i++) trail(p, ((t * speed + i / n) % 1), 6, id === "records_glimmer" ? CRUST : CBLUE, 0.2);
    }
    // After the shim the call carries context: a bigger bead with a rust partner.
    { const p = paths.shim_model; for (let i = 0; i < 2; i++) { const u = (t * 0.32 + i / 2) % 1; trail(p, u, 6, CBLUE, 0.28); trail(p, (u + 0.04) % 1, 3, CRUST, 0.2); } }

    // The Task.
    const story = taskStory(storyTime(s, st, t));
    hero.visible = !!story.pos;
    if (story.pos) { hero.position.set(...story.pos); heroPos.copy(hero.position); }
    hero.material = story.bad ? M.rust : story.isObject ? M.white : M.blue;
    heroTag.material = story.isObject ? M.blue : M.white;
    const setArc = (w, lit, col) => w.arcs.forEach((a, i) => a.material.color.set(i < lit ? col : "#D8D1C1"));
    const beat = (w, on, rate = 1.1) => {
      const c = (t * rate) % 1;
      w.ripple.material.opacity = on ? (1 - c) * 0.7 : 0;
      w.ripple.scale.setScalar(on ? 0.4 + c * 2 : 0.4);
    };
    setArc(Wa, story.claimA ? 3 - story.missed : story.stoppedA ? 0 : 3, story.bad ? RUST : BLUE);
    setArc(Wb, 3, BLUE);
    setArc(Wc, 3, RUST);
    beat(Wa, story.claimA && !story.bad); beat(Wb, story.claimB); beat(Wc, story.checking, 1.6);
    Wa.lamp.material = story.bad || story.stoppedA ? M.off : M.glow;
    const stretch = (w, on, to) => {
      w.arm.visible = !!on;
      if (!on) return;
      const a = V(w.pos.x, 2.4, w.pos.z + 1), b = to.clone();
      w.arm.position.copy(a).add(b).multiplyScalar(0.5); w.arm.lookAt(b); w.arm.scale.set(1, 1, Math.max(0.05, a.distanceTo(b)));
    };
    stretch(Wa, story.claimA, heroPos); stretch(Wb, story.claimB, heroPos);

    // Tasks waiting on the belt.
    for (let i = 0; i < 7; i++) {
      const x = belt0 + ((t * 0.32 + i * 2.8) % beltL), edge = Math.min(1, Math.min(x - belt0, belt0 + beltL - x) / 0.6);
      place(waiting, i, x, BELT_Y - 0.03, AT.queue.z, Math.max(0.01, edge));
    }
    waiting.instanceMatrix.needsUpdate = true;

    // Kept versions: towers grow; the newest slab drops in.
    let n = 0;
    const keptAt = partsAt("store"), grow = s && s.kind === "parts" && keptAt >= 0 && st >= keptAt ? clamp((st - keptAt) / 3.6) : 1;
    TOWERS.forEach(([dx, dz, count], i) => {
      const shown = Math.ceil(count * Math.max(0.4, grow));
      for (let k = 0; k < shown - 1; k++) { place(versionsOld, n++, AT.store.x + dx, 0.52 + k * 0.4, AT.store.z + dz); }
      place(versionsTop, i, AT.store.x + dx, 0.52 + (shown - 1) * 0.4 + (1 - smooth(((t * 0.7 + i * 0.4) % 1) * 3)) * 0.8, AT.store.z + dz);
    });
    versionsOld.count = n; versionsOld.instanceMatrix.needsUpdate = true; versionsTop.instanceMatrix.needsUpdate = true;

    // Task Objects on their way to the shim, as cards.
    for (let i = 0; i < 16; i++) {
      const u = ((t * 0.09 + i / 16) % 1), q = paths.store_shim.curve.getPointAt(u), f = Math.min(1, Math.min(u, 1 - u) / 0.05);
      place(contextCards, i, q.x, q.y + 0.28, q.z, Math.max(0.01, f), Math.max(0.01, f), 0, u * 3);
    }
    contextCards.instanceMatrix.needsUpdate = true;

    // Glimmer's 52 layers: a slow wave travels up through them.
    for (let i = 0; i < LAYERS; i++) {
      const y = 0.9 + i * layerH, wave = Math.sin(i * 0.26 - t * 1.6) * 0.14, r = 2 - (i / LAYERS) * 0.7 + wave;
      place(layers, i, AT.glimmer.x, y, AT.glimmer.z, r, 1);
      layers.setColorAt(i, tmpC.set(BLUE).lerp(CPAPER, 0.15 + (Math.sin(i * 0.26 - t * 1.6) + 1) * 0.26));
    }
    layers.instanceMatrix.needsUpdate = true; layers.instanceColor.needsUpdate = true;

    // Small lives.
    brain.rotation.y = t * 0.2;
    key.rotation.y = t * 0.9;
    screenBars.forEach((b, i) => { const w = 0.5 + ((Math.sin(t * 0.7 + i * 1.7) + 1) / 2) * 2; b.scale.x = w; b.position.x = -1.5 + w / 2; });
    dish.rotation.y = Math.sin(t * 0.4) * 0.25;
    dialHand.position.set(Math.sin(t * 0.5) * 0.62, Math.cos(t * 0.5) * 0.62, 0.19); dialHand.rotation.z = -t * 0.5;
    for (let i = 0; i < 5; i++) { const a = t * 0.5 + (i * Math.PI * 2) / 5; place(settings, i, AT.omni.x + Math.cos(a) * 2.9, 2.5 + Math.sin(t + i) * 0.2, AT.omni.z + Math.sin(a) * 2.9, 1, 1, 0, a); }
    settings.instanceMatrix.needsUpdate = true;
    { const a = t * 2.2; loopBead.position.set(loopPos.x + Math.cos(a) * 0.85, 1.6 + Math.sin(a) * 0.85 * Math.cos(0.25), loopPos.z + Math.sin(a) * 0.85 * Math.sin(0.25)); }

    beads.count = beadN; beads.instanceMatrix.needsUpdate = true; if (beads.instanceColor) beads.instanceColor.needsUpdate = true;

    // The spot under the current subject.
    const f0 = shot.prev.f, f1 = shot.cur.f, sk = smooth(shot.k * 1.4), hasSpot = shot.cur.hi !== null;
    const px = lerp(f0.at.x, f1.at.x, sk), pz = lerp(f0.at.z, f1.at.z, sk), pr = Math.max(0.1, lerp(f0.r, f1.r, sk));
    for (const m of [spot, spotFill]) { m.position.x = px; m.position.z = pz; m.scale.set(pr, pr * lerp(f0.e || 1, f1.e || 1, sk), 1); m.visible = hasSpot && pr > 0.2; }
    spot.material.opacity = 0.55 + Math.sin(t * 2.6) * 0.25;
    return story;
  }

  // ---- Labels, projected from the world and drawn on the 2D canvas so they stay sharp at any size.
  const lastBox = {};
  const proj = new T.Vector3();
  const anchors = {
    agent: V(-24, 4.3, -2), http: V(-20, 0.9, 2.2), gate: V(-15, 7.1, 5), queue: V(-10.5, 2.2, 6.2), spark: V(-7, 4.5, 1), wonder: V(-1.5, 4.5, 1), checker: V(5, 4.5, 1),
    store: V(14, 5, 0), feeds: V(23, 4.6, 6), shim: V(-10, 5.9, -10), model: V(2, 4.6, -10), glimmer: V(18, 8.8, -13), records: V(13.5, 1.6, -9.5),
    eranos: V(-33, 4.4, 4), omni: V(3, 4.6, 24), reuse: V(0, 1.1, -6), tuning: V(9, 5, 12.5),
  };
  for (let i = 0; i < 5; i++) { const p = bayAt(i); anchors[`bay${i}`] = V(p.x, 2.8, p.z); }
  function project(v3, W, H) {
    proj.copy(v3).project(camera);
    if (proj.z > 1 || proj.z < -1) return null;
    return [(proj.x * 0.5 + 0.5) * W, (-proj.y * 0.5 + 0.5) * H];
  }
  function roundRect(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
  function wrapText(c, s, maxW) {
    const out = []; let line = "";
    for (const w of s.split(" ")) { const n = line ? `${line} ${w}` : w; if (c.measureText(n).width > maxW && line) { out.push(line); line = w; } else line = n; }
    if (line) out.push(line);
    return out;
  }
  function drawLabels(c, W, H, list, safeTop, safeBottom) {
    const phone = W < 700, ls = phone ? 1 : Math.max(0.9, Math.min(W / 1280, 1.35));
    const placed = [{ x: 0, y: 0, w: W, h: safeTop }, { x: 0, y: H - safeBottom, w: W, h: safeBottom }];
    const hit = (b) => placed.some((p) => b.x < p.x + p.w + 4 && b.x + b.w + 4 > p.x && b.y < p.y + p.h + 4 && b.y + b.h + 4 > p.y);
    const drawn = [];
    for (const l of list) {
      const p = l.at && project(l.at, W, H);
      if (!p) continue;
      const big = l.hero, kind = l.tag ? "tag" : big ? "hero" : "plain";
      const nameSize = kind === "hero" ? (phone ? 18 : 25 * ls) : kind === "tag" ? (phone ? 12 : 14 * ls) : (phone ? 12 : 15 * ls);
      const subSize = phone ? 13 : 16 * ls, pad = kind === "hero" ? 12 * (phone ? 0.8 : ls) : 7;
      c.font = `700 ${nameSize}px ${api.FONT}`;
      const maxW = Math.min(W - 28, phone ? W - 28 : 520 * ls);
      const nameLines = wrapText(c, l.name, maxW - pad * 2);
      let w = Math.max(...nameLines.map((s) => c.measureText(s).width));
      let subLines = [];
      if (big && l.sub) { c.font = `400 ${subSize}px ${api.FONT}`; subLines = wrapText(c, l.sub, maxW - pad * 2); w = Math.max(w, ...subLines.map((s) => c.measureText(s).width)); }
      const lhN = nameSize * 1.22, lhS = subSize * 1.32;
      const bw = w + pad * 2, bh = nameLines.length * lhN + subLines.length * lhS + pad * (kind === "hero" ? 1.5 : 1.1);
      const lift = kind === "hero" ? 34 : kind === "tag" ? 10 : 18;
      const cands = big ? [[0, -lift], [0, -lift - 40], [bw * 0.55, -lift], [-bw * 0.55, -lift], [0, -lift - 90], [bw * 0.6, -lift - 60], [-bw * 0.6, -lift - 60], [0, lift + bh * 0.4]] : [[0, -lift], [bw * 0.6, -lift + 4], [-bw * 0.6, -lift + 4], [0, -lift - 26], [0, bh + lift]];
      let box = null;
      for (const [dx, dy] of cands) {
        const b = { x: Math.max(8, Math.min(W - 8 - bw, p[0] + dx - bw / 2)), y: p[1] + dy - bh, w: bw, h: bh };
        if (b.y < 2 || b.y + bh > H - 2) continue;
        if (!hit(b)) { box = b; break; }
      }
      if (!box) {
        if (!big) continue;
        box = { x: Math.max(8, Math.min(W - 8 - bw, p[0] - bw / 2)), y: Math.max(safeTop + 4, Math.min(H - safeBottom - bh - 4, p[1] - lift - bh)), w: bw, h: bh };
      }
      // Ease the card toward its slot, so a change of slot doesn't jump.
      const prev = lastBox[l.id];
      if (prev && Math.abs(prev.x - box.x) + Math.abs(prev.y - box.y) < 200) { box.x = lerp(prev.x, box.x, 0.28); box.y = lerp(prev.y, box.y, 0.28); }
      lastBox[l.id] = box;
      placed.push(box);
      drawn.push({ l, p, box, nameLines, subLines, nameSize, subSize, lhN, lhS, pad, kind });
    }
    for (const d of drawn.reverse()) {
      const { l, p, box, kind } = d, col = l.col || (kind === "hero" ? BLUE : INK);
      c.globalAlpha = l.alpha === undefined ? 1 : l.alpha;
      c.strokeStyle = kind === "hero" ? col : "#8A8476"; c.lineWidth = kind === "hero" ? 2 : 1;
      if (kind !== "tag") {
        c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(box.x + box.w / 2, box.y + box.h); c.stroke();
        c.fillStyle = col; c.beginPath(); c.arc(p[0], p[1], kind === "hero" ? 4 : 2.5, 0, Math.PI * 2); c.fill();
      }
      c.fillStyle = CARD; c.globalAlpha *= 0.96;
      roundRect(c, box.x, box.y, box.w, box.h, 5); c.fill(); c.globalAlpha = l.alpha === undefined ? 1 : l.alpha;
      c.strokeStyle = kind === "hero" ? col : "#CFC8B8"; c.lineWidth = kind === "hero" ? 2 : 1; c.stroke();
      c.textAlign = "left"; c.textBaseline = "alphabetic";
      let y = box.y + d.pad * 0.55 + d.nameSize;
      c.font = `700 ${d.nameSize}px ${api.FONT}`; c.fillStyle = col;
      for (const s of d.nameLines) { c.fillText(s, box.x + d.pad, y); y += d.lhN; }
      y += d.subSize * 0.02 - d.lhN + d.lhS;
      c.font = `400 ${d.subSize}px ${api.FONT}`; c.fillStyle = SOFT;
      for (const s of d.subLines) { c.fillText(s, box.x + d.pad, y); y += d.lhS; }
      c.globalAlpha = 1;
    }
  }

  // ---- Heading and caption: the page's own sentences on a soft plate, sized to stay readable on a phone.
  function plate(c, W, y0, y1, a = 0.88) {
    c.save(); c.globalAlpha = a; c.fillStyle = PAPER; c.fillRect(0, y0, W, y1 - y0); c.restore();
  }
  const measureLines = (c, runs, size, weight, maxW) => {
    c.font = `${weight} ${size}px ${api.FONT}`;
    const cw = c.measureText("0").width;
    return api.wrap(api.chars(runs), Math.max(8, Math.floor(maxW / cw))).length;
  };
  function writeHead(c, v, st, runs) {
    const { W, H } = v, phone = W < 700, size = phone ? 19 : Math.max(24, 34 * Math.min(W / 1280, H / 720)), lh = size * 1.25, maxW = W * (phone ? 0.92 : 0.86);
    const n = measureLines(c, runs, size, 700, maxW);
    const top = size * 0.7;
    plate(c, W, 0, top + n * lh + size * 0.15, 0.82);
    api.text(runs, { x: W / 2, y: top + size * 0.9, size, lh: 1.25, weight: 700, align: "center", maxW, shown: api.typed({ t: st }, 0, 46) });
    return top + n * lh + size * 0.2;
  }
  function writeCaption(c, v, runs, alpha) {
    const { W, H } = v, phone = W < 700, size = phone ? 15 : Math.max(18, 24 * Math.min(W / 1280, H / 720)), lh = size * 1.3, maxW = W * (phone ? 0.92 : 0.8);
    const n = measureLines(c, runs, size, 400, maxW), h = n * lh + size * 0.9, y0 = H - h - 6;
    if (alpha > 0) {
      c.save(); c.globalAlpha = 0.9 * alpha; c.fillStyle = CARD; c.fillRect(0, y0, W, h + 6); c.restore();
      api.text(runs, { x: W / 2, y: y0 + size * 1.08, size, lh: 1.3, align: "center", maxW, alpha, color: SOFT });
    }
    return h + 8;
  }
  const label = (id, extra = {}) => { const b = L[id] || []; return { id, at: anchors[id], name: b[0], sub: b[1], ...extra }; };
  const nameOf = (runs) => api.chars(runs).map((q) => q.ch).join("");

  function caption(kind, s, st) {
    const steps = s.steps, ps = s.ps;
    const pick = (list, times) => { let i = -1; times.forEach((t0, k) => { if (st >= t0) i = k; }); return i < 0 ? null : { runs: list[i], a: clamp((st - times[i]) / 0.35), i }; };
    if (kind === "parts") return pick(steps, steps.map((_, i) => partsStart + i * partsEach));
    if (kind === "file") return pick([...steps, ps[0]], [1, 2.2, 3.4, 4.6, 5.8]);
    if (kind === "omninode") return pick([ps[0], ...steps], [0.9, ...steps.map((_, i) => omniStart + i * omniEach)]);
    if (kind === "queue") return pick(steps, [0, 1.4, 4.2, 6.6, 9.2]);
    if (kind === "workers") return pick(ps, [0.2, 2]);
    if (kind === "reuse") return pick(ps, [5]);
    if (kind === "eranos") return pick(ps, [3, 8]);
    return null;
  }

  function labelsFor(kind, s, st, shot, story) {
    const hi = shot.cur.hi, list = [];
    const overview = shot.cur.name === "overview" && shot.k > 0.6;
    const nearOf = { agent: ["http"], http: ["agent", "gate", "eranos"], gate: ["queue", "agent"], queue: ["gate", "spark", "wonder"], spark: ["wonder"], wonder: ["spark", "checker"], checker: ["wonder", "store"], store: ["checker", "feeds"], feeds: ["store"], shim: ["model", "agent"], reuse: ["shim", "store", "model"], model: ["shim"], glimmer: ["records"], eranos: ["gate"], omni: [], tuning: ["store", "wonder"] };
    let hero = null;
    if (hi) {
      if (hi.startsWith("bay")) { const i = Number(hi.slice(3)), txt = nameOf(s.steps[i]), d = txt.indexOf(":"); hero = { id: hi, at: anchors[hi], name: txt.slice(0, d), sub: txt.slice(d + 1).trim() }; hero.sub = hero.sub.charAt(0).toUpperCase() + hero.sub.slice(1); }
      else hero = label(hi);
      // The same station says more at its moment in the story.
      if (kind === "queue" && hi === "spark") hero.sub = st < 4.2 ? L.claim[0] : L.missed[0];
      if (kind === "queue" && hi === "wonder") hero.sub = L.wonder[1];
      if (kind === "workers" && hi === "wonder") hero.sub = L.workers[0];
      hero.hero = true;
      if (hi === "store" || hi === "checker") hero.col = hi === "checker" ? RUST : BLUE;
      list.push(hero);
    }
    if (overview) {
      for (const id of ["gate", "queue", "store", "shim", "agent", "glimmer", "spark", "wonder", "checker", "eranos", "feeds", "model", "omni", "tuning", "records"]) list.push(label(id));
    } else if (hi && nearOf[hi]) {
      for (const id of nearOf[hi]) list.push(label(id));
    } else if (hi && hi.startsWith("bay")) {
      list.push(label("omni"));
    }
    // Tags that belong to a moment.
    if (story.pos && (kind === "queue" || (kind === "parts" && hi === "queue"))) list.unshift({ id: "task", tag: true, at: heroPos.clone().setY(heroPos.y + 0.75), name: story.isObject ? L.object[0] : L.task[0], col: story.bad ? RUST : BLUE });
    if (hi === "store") TOWERS.slice(0, 3).forEach(([dx, dz, count], i) => list.push({ id: `v${i}`, tag: true, at: V(AT.store.x + dx - 1, 0.6 + (i * 0.9) + 0.6, AT.store.z + dz + 1), name: words.world.versions[i] }));
    if (hi === "omni" && st < omniStart) words.world.settings.forEach((n, i) => { const a = t0(st) * 0.5 + (i * Math.PI * 2) / 5; list.push({ id: `set${i}`, tag: true, at: V(AT.omni.x + Math.cos(a) * 2.9, 2.8, AT.omni.z + Math.sin(a) * 2.9), name: n }); });
    if (hi === "eranos" && kind === "eranos") { list.push({ id: "door1", tag: true, at: V(AT.eranos.x - 1.3, 1, AT.eranos.z + 2), name: L.door1[0], col: BLUE }); list.push({ id: "door2", tag: true, at: V(AT.eranos.x + 1.3, 1, AT.eranos.z + 2), name: L.door2[0], col: RUST }); }
    return list;
  }
  let lastT = 0;
  const t0 = () => lastT;

  // Adaptive sharpness: starts at the device's ratio capped at 2, and steps down when frames run long.
  let scale = 1, slowFor = 0, fastFor = 0, lastFrame = 0, ema = 16, frames = 0, maxTris = 0;
  function setSize(W, H, dpr) {
    const want = Math.max(1, dpr * scale), pw = Math.round(W * want), ph = Math.round(H * want);
    if (gl.width !== pw || gl.height !== ph) { renderer.setPixelRatio(want); renderer.setSize(W, H, false); }
    aspect = W / H; camera.aspect = aspect; camera.updateProjectionMatrix();
  }

  return {
    has: (kind) => alive && WORLD_KINDS.has(kind),
    stats: () => ({ triangles: maxTris, calls: renderer.info.render.calls, ema: Math.round(ema * 10) / 10, scale, frames, pixelRatio: renderer.getPixelRatio() }),
    draw(c, v, filmT, next) {
      const { W, H, t: st, s } = v;
      lastT = filmT;
      const dpr = Math.min(devicePixelRatio || 1, 2);
      setSize(W, H, dpr);
      const shot = moveCamera(filmT);
      const story = update(filmT, s, st, shot);
      renderer.render(scene, camera);
      maxTris = Math.max(maxTris, renderer.info.render.triangles);
      c.drawImage(gl, 0, 0, W, H);

      const top = writeHead(c, v, st, s.h);
      const cap = caption(s.kind, s, st);
      const reserve = cap ? writeCaption(c, v, cap.runs, cap.a) : 0;
      drawLabels(c, W, H, labelsFor(s.kind, s, st, shot, story), top, Math.max(reserve, 8));

      // Into and out of the world from flat scenes: through paper, never a jump cut.
      const inA = s.prevWorld ? 0 : 1 - clamp(st / 0.8), outA = next ? 0 : 1 - clamp((s.secs - st) / 0.5), veil = Math.max(inA, outA);
      if (veil > 0) { c.save(); c.globalAlpha = veil; c.fillStyle = PAPER; c.fillRect(0, 0, W, H); c.restore(); }

      const now = performance.now();
      if (lastFrame) {
        const dt = now - lastFrame;
        if (dt < 200) {
          ema = ema * 0.94 + dt * 0.06; frames++;
          if (ema > 30) { slowFor += dt; fastFor = 0; } else if (ema < 18) { fastFor += dt; slowFor = 0; } else { slowFor = 0; fastFor = 0; }
          if (slowFor > 1500 && scale > 0.5) { scale = Math.max(0.5, scale * 0.8); slowFor = 0; }
          if (fastFor > 6000 && scale < 1) { scale = Math.min(1, scale * 1.15); fastFor = 0; }
        }
      }
      lastFrame = now;
    },
    dispose() { alive = false; renderer.dispose(); },
  };
}
