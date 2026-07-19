/**
 * FABLE 5 NEURAL CORE — vector index
 * In-memory cosine/euclidean engine + helpers shared with the Qdrant API path.
 */

export interface VectorDocument {
  id: string;
  title: string;
  category: "strategy" | "pattern" | "trade_cluster" | "market_alert";
  vector: number[]; // 8-d: [ProfitFactor, WinRate, Volatility, Drawdown, CapitalLeverage, MarketSentiment, TimeDecay, NeuralRisk]
  metadata: {
    description: string;
    assetClass?: string;
    targetTimeframe?: string;
    profitFactor?: number;
    winRate?: number;
    volatility?: number;
    drawdown?: number;
    [key: string]: unknown;
  };
}

export type DistanceMetric = "cosine" | "euclidean" | "dot_product";

export const DEFAULT_SEED_DOCUMENTS: VectorDocument[] = [
  {
    id: "VEC-SMC01",
    title: "Smart Money Concepts (SMC) Sweeper",
    category: "strategy",
    vector: [0.85, 0.72, 0.45, 0.12, 0.6, 0.8, 0.3, 0.25],
    metadata: {
      description: "Detects order block sweeps, liquidity runs, and fair value gaps.",
      assetClass: "Crypto/Forex",
      targetTimeframe: "5m/15m",
      profitFactor: 2.8,
      winRate: 72,
      volatility: 45,
      drawdown: 12,
    },
  },
  {
    id: "VEC-BBRSI",
    title: "Bollinger Bands + RSI Mean Reversion",
    category: "strategy",
    vector: [0.65, 0.58, 0.3, 0.18, 0.4, 0.5, 0.15, 0.35],
    metadata: {
      description: "Tactical mean-reversion counter-trend rig suited for tight consolidations.",
      assetClass: "Crypto/Equities",
      targetTimeframe: "1h",
      profitFactor: 1.9,
      winRate: 58,
      volatility: 30,
      drawdown: 18,
    },
  },
  {
    id: "VEC-TRL02",
    title: "Dynamic Trailing Stop Momentum Rig",
    category: "strategy",
    vector: [0.92, 0.61, 0.85, 0.28, 0.75, 0.9, 0.65, 0.55],
    metadata: {
      description:
        "Exploits high-volatility breakouts, lock-stepping profit targets with trailing stop vectors.",
      assetClass: "Crypto/EV Equities",
      targetTimeframe: "5m/1h",
      profitFactor: 3.1,
      winRate: 61,
      volatility: 85,
      drawdown: 28,
    },
  },
  {
    id: "VEC-OB042",
    title: "Institutional Order Block Swallower",
    category: "pattern",
    vector: [0.78, 0.68, 0.5, 0.14, 0.5, 0.75, 0.2, 0.2],
    metadata: {
      description: "Spots order swallow behaviors where large institutions absorb retail sell orders.",
      assetClass: "Multi-Asset",
      targetTimeframe: "15m/4h",
      profitFactor: 2.4,
      winRate: 68,
      volatility: 50,
      drawdown: 14,
    },
  },
  {
    id: "VEC-BRK33",
    title: "Bearish Breakout Trap Safeguard",
    category: "pattern",
    vector: [0.55, 0.52, 0.7, 0.35, 0.3, 0.2, 0.4, 0.8],
    metadata: {
      description: "High stress index structure that triggers when support is swept and quickly reclaimed.",
      assetClass: "Crypto/Indices",
      targetTimeframe: "15m",
      profitFactor: 1.4,
      winRate: 52,
      volatility: 70,
      drawdown: 35,
    },
  },
  {
    id: "VEC-NIO45",
    title: "High-Beta EV Electric Vector Rig",
    category: "trade_cluster",
    vector: [0.74, 0.64, 0.78, 0.25, 0.7, 0.85, 0.5, 0.45],
    metadata: {
      description: "Specialized model tuned to capture high volatility momentum in EV stocks like NIO.",
      assetClass: "Equities (NIO)",
      targetTimeframe: "1h/1d",
      profitFactor: 2.3,
      winRate: 64,
      volatility: 78,
      drawdown: 25,
    },
  },
];

export class InMemoryVectorIndex {
  private documents: VectorDocument[] = [];
  private dimensions: number = 8;

  constructor(dimensions: number = 8) {
    this.dimensions = dimensions;
    this.seedDefaults();
  }

  public dotProduct(v1: number[], v2: number[]): number {
    if (v1.length !== v2.length) {
      throw new Error(`Dimensionality mismatch. v1: ${v1.length}, v2: ${v2.length}`);
    }
    let dot = 0;
    for (let i = 0; i < v1.length; i++) {
      dot += v1[i] * v2[i];
    }
    return dot;
  }

  public magnitude(v: number[]): number {
    let sum = 0;
    for (let i = 0; i < v.length; i++) {
      sum += v[i] * v[i];
    }
    return Math.sqrt(sum);
  }

  public cosineSimilarity(v1: number[], v2: number[]): number {
    const dot = this.dotProduct(v1, v2);
    const mag1 = this.magnitude(v1);
    const mag2 = this.magnitude(v2);
    if (mag1 === 0 || mag2 === 0) return 0;
    return dot / (mag1 * mag2);
  }

  public euclideanDistance(v1: number[], v2: number[]): number {
    if (v1.length !== v2.length) {
      throw new Error("Dimensionality mismatch for Euclidean distance.");
    }
    let sum = 0;
    for (let i = 0; i < v1.length; i++) {
      const diff = v1[i] - v2[i];
      sum += diff * diff;
    }
    return Math.sqrt(sum);
  }

  public add(doc: Omit<VectorDocument, "id"> & {id?: string}): VectorDocument {
    const id = doc.id || `VEC-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;
    const newDoc: VectorDocument = {
      id,
      title: doc.title,
      category: doc.category,
      vector: this.normalizeOrTruncate(doc.vector),
      metadata: doc.metadata,
    };
    this.documents.push(newDoc);
    return newDoc;
  }

  public listAll(): VectorDocument[] {
    return [...this.documents];
  }

  public query(
    queryVector: number[],
    topK: number = 4,
    metric: DistanceMetric = "cosine",
  ): {document: VectorDocument; score: number}[] {
    const normalizedQuery = this.normalizeOrTruncate(queryVector);

    const scored = this.documents.map((doc) => {
      let score = 0;
      if (metric === "cosine") {
        score = this.cosineSimilarity(normalizedQuery, doc.vector);
      } else if (metric === "dot_product") {
        score = this.dotProduct(normalizedQuery, doc.vector);
      } else {
        const dist = this.euclideanDistance(normalizedQuery, doc.vector);
        score = 1 / (1 + dist);
      }
      return {document: doc, score};
    });

    return scored.sort((a, b) => b.score - a.score).slice(0, topK);
  }

  public delete(id: string): boolean {
    const initialLen = this.documents.length;
    this.documents = this.documents.filter((d) => d.id !== id);
    return this.documents.length < initialLen;
  }

  public embedText(text: string, tags: string[] = []): number[] {
    const clean = (text + tags.join(" ")).toLowerCase();

    return new Array(this.dimensions).fill(0).map((_, index) => {
      let sum = 0;
      for (let i = 0; i < clean.length; i++) {
        sum += clean.charCodeAt(i) * (i + 1) * (index + 3);
      }
      return 0.05 + ((sum % 1000) / 1000) * 0.94;
    });
  }

  private normalizeOrTruncate(vec: number[]): number[] {
    if (vec.length === this.dimensions) return vec;
    if (vec.length > this.dimensions) return vec.slice(0, this.dimensions);
    const filled = [...vec];
    while (filled.length < this.dimensions) {
      filled.push(0.0);
    }
    return filled;
  }

  private seedDefaults() {
    this.documents = DEFAULT_SEED_DOCUMENTS.map((doc) => ({
      ...doc,
      vector: [...doc.vector],
      metadata: {...doc.metadata},
    }));
  }
}
