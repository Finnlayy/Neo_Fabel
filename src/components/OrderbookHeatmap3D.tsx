import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { fetchOrderBook } from "../api/market";

type Level = { price: number; volume: number };
type Book = { pair: string; bids: Level[]; asks: Level[] };

type Props = {
  pair?: string;
  language: "en" | "de";
  pollMs?: number;
};

export default function OrderbookHeatmap3D({ pair = "ADAUSD", language, pollMs = 2500 }: Props) {
  const de = language === "de";
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [mid, setMid] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const bookRef = useRef<Book | null>(null);

  const title = useMemo(
    () => (de ? `Orderbuch-Heatmap · ${pair}` : `Order book heatmap · ${pair}`),
    [de, pair],
  );

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const raw = await fetchOrderBook(pair, 36);
        if (!alive) return;
        const book: Book = {
          pair: raw.pair,
          bids: raw.bids.map((l) => ({ price: l.price, volume: l.volume })),
          asks: raw.asks.map((l) => ({ price: l.price, volume: l.volume })),
        };
        bookRef.current = book;
        const bestBid = book.bids[0]?.price;
        const bestAsk = book.asks[0]?.price;
        if (bestBid && bestAsk) setMid((bestBid + bestAsk) / 2);
        setErr(null);
      } catch (e) {
        if (alive) setErr(String(e));
      }
    }
    void poll();
    const id = window.setInterval(() => void poll(), pollMs);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [pair, pollMs]);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    const width = el.clientWidth || 640;
    const height = 280;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020617);
    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 200);
    camera.position.set(18, 16, 22);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    el.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0xffffff, 0.55);
    const dir = new THREE.DirectionalLight(0xffffff, 0.85);
    dir.position.set(8, 20, 10);
    scene.add(ambient, dir);

    const grid = new THREE.GridHelper(40, 20, 0x1e293b, 0x0f172a);
    scene.add(grid);

    const bars = new THREE.Group();
    scene.add(bars);

    const maxBars = 72;
    const meshes: THREE.Mesh[] = [];
    for (let i = 0; i < maxBars; i++) {
      const geo = new THREE.BoxGeometry(0.7, 1, 0.7);
      const mat = new THREE.MeshStandardMaterial({ color: 0x22d3ee, roughness: 0.35, metalness: 0.1 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.visible = false;
      bars.add(mesh);
      meshes.push(mesh);
    }

    let frame = 0;
    let raf = 0;
    const animate = () => {
      frame += 1;
      bars.rotation.y = Math.sin(frame * 0.004) * 0.25;
      const book = bookRef.current;
      if (book) {
        const levels = [
          ...book.bids.slice(0, 36).map((l) => ({ ...l, side: "bid" as const })),
          ...book.asks.slice(0, 36).map((l) => ({ ...l, side: "ask" as const })),
        ];
        const maxVol = Math.max(1e-9, ...levels.map((l) => l.volume));
        levels.forEach((lvl, i) => {
          const mesh = meshes[i];
          if (!mesh) return;
          const h = 0.4 + (lvl.volume / maxVol) * 8;
          mesh.visible = true;
          mesh.scale.y = h;
          const x = (i % 36) - 18;
          const z = lvl.side === "bid" ? -4 : 4;
          mesh.position.set(x * 0.85, h / 2, z);
          const mat = mesh.material as THREE.MeshStandardMaterial;
          mat.color.set(lvl.side === "bid" ? 0x34d399 : 0xfb7185);
          mat.emissive.set(lvl.side === "bid" ? 0x064e3b : 0x7f1d1d);
          mat.emissiveIntensity = 0.25 + (lvl.volume / maxVol) * 0.55;
        });
        for (let i = levels.length; i < meshes.length; i++) meshes[i].visible = false;
      }
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);

    const onResize = () => {
      const w = el.clientWidth || width;
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
      renderer.setSize(w, height);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      if (renderer.domElement.parentElement === el) el.removeChild(renderer.domElement);
      meshes.forEach((m) => {
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      });
    };
  }, []);

  return (
    <section className="rounded-xl border border-fuchsia-500/20 bg-slate-950/70 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/5">
        <h3 className="text-[11px] font-bold uppercase tracking-widest text-fuchsia-300">{title}</h3>
        <span className="text-[9px] font-mono text-slate-400">
          mid {mid != null ? mid.toFixed(6) : "—"}
        </span>
      </div>
      {err && <p className="px-4 py-1 text-[10px] text-rose-400">{err}</p>}
      <div ref={mountRef} className="w-full h-[280px]" />
      <p className="px-4 py-2 text-[9px] text-slate-500">
        {de
          ? "Live L2 via /api/v1/market/orderbook — Höhe = Volume, Grün=Bids / Rosa=Asks."
          : "Live L2 via /api/v1/market/orderbook — bar height = volume, green=bids / pink=asks."}
      </p>
    </section>
  );
}
