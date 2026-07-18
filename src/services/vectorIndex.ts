/**
 * FABLE 5 NEURAL CORE - HIGHLY OPTIMIZED IN-MEMORY VECTOR INDEX
 * Provides full high-performance mathematical Operations (Cosine Similarity, Euclidean Distance),
 * vector embeddings simulation for trading strategies, and indexing capabilities.
 */

export interface VectorDocument {
  id: string;
  title: string;
  category: "strategy" | "pattern" | "trade_cluster" | "market_alert";
  vector: number[]; // e.g. 8-dimensional space: [ProfitFactor, WinRate, Volatility, Drawdown, CapitalLeverage, MarketSentiment, TimeDecay, NeuralRisk]
  metadata: {
    description: string;
    assetClass?: string;
    targetTimeframe?: string;
    profitFactor?: number;
    winRate?: number;
    volatility?: number;
    drawdown?: number;
    [key: string]: any;
  };
}

export type DistanceMetric = "cosine" | "euclidean" | "dot_product";

export class InMemoryVectorIndex {
  private documents: VectorDocument[] = [];
  private dimensions: number = 8;

  constructor(dimensions: number = 8) {
    this.dimensions = dimensions;
    this.seedDefaults();
  }

  /**
   * Calculates Dot Product of two vectors of identical length
   */
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

  /**
   * Calculates L2 Norm (magnitude) of a vector
   */
  public magnitude(v: number[]): number {
    let sum = 0;
    for (let i = 0; i < v.length; i++) {
      sum += v[i] * v[i];
    }
    return Math.sqrt(sum);
  }

  /**
   * Computes the Cosine Similarity between two vectors: (A . B) / (||A|| * ||B||)
   * Yields a value between -1.0 and 1.0 (typically 0.0 to 1.0 for positive spaces)
   */
  public cosineSimilarity(v1: number[], v2: number[]): number {
    const dot = this.dotProduct(v1, v2);
    const mag1 = this.magnitude(v1);
    const mag2 = this.magnitude(v2);
    if (mag1 === 0 || mag2 === 0) return 0;
    return dot / (mag1 * mag2);
  }

  /**
   * Computes Euclidean (L2) distance: sqrt(sum((a_i - b_i)^2))
   */
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

  /**
   * Adds a new vector document to the in-memory index
   */
  public add(doc: Omit<VectorDocument, "id"> & { id?: string }): VectorDocument {
    const id = doc.id || `VEC-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;
    const newDoc: VectorDocument = {
      id,
      title: doc.title,
      category: doc.category,
      vector: this.normalizeOrTruncate(doc.vector),
      metadata: doc.metadata
    };
    this.documents.push(newDoc);
    return newDoc;
  }

  /**
   * Retrieves all registered vectors
   */
  public listAll(): VectorDocument[] {
    return [...this.documents];
  }

  /**
   * Queries the top K most similar vector documents using specified metric
   */
  public query(
    queryVector: number[],
    topK: number = 4,
    metric: DistanceMetric = "cosine"
  ): { document: VectorDocument; score: number }[] {
    const normalizedQuery = this.normalizeOrTruncate(queryVector);

    const scored = this.documents.map((doc) => {
      let score = 0;
      if (metric === "cosine") {
        score = this.cosineSimilarity(normalizedQuery, doc.vector);
      } else if (metric === "dot_product") {
        score = this.dotProduct(normalizedQuery, doc.vector);
      } else {
        // Euclidean - lower is better, convert to a pseudo-similarity score: 1 / (1 + distance)
        const dist = this.euclideanDistance(normalizedQuery, doc.vector);
        score = 1 / (1 + dist);
      }
      return { document: doc, score };
    });

    // Sort descending by score
    return scored.sort((a, b) => b.score - a.score).slice(0, topK);
  }

  /**
   * Deletes a document by ID
   */
  public delete(id: string): boolean {
    const initialLen = this.documents.length;
    this.documents = this.documents.filter((d) => d.id !== id);
    return this.documents.length < initialLen;
  }

  /**
   * Truncates or pads arrays to maintain static vector dimension
   */
  private normalizeOrTruncate(vec: number[]): number[] {
    if (vec.length === this.dimensions) return vec;
    if (vec.length > this.dimensions) return vec.slice(0, this.dimensions);
    const filled = [...vec];
    while (filled.length < this.dimensions) {
      filled.push(0.0);
    }
    return filled;
  }

  /**
   * Generates a deterministic high-fidelity mock vector from textual parameters
   */
  public embedText(text: string, tags: string[] = []): number[] {
    const clean = (text + tags.join(" ")).toLowerCase();
    
    // Create deterministic weights using simple hash coefficients
    const vec = new Array(this.dimensions).fill(0).map((_, index) => {
      let sum = 0;
      for (let i = 0; i < clean.length; i++) {
        sum += clean.charCodeAt(i) * (i + 1) * (index + 3);
      }
      // Map to 0.05 - 0.99 range
      return 0.05 + ((sum % 1000) / 1000) * 0.94;
    });

    return vec;
  }

  /**
   * Seeds default state-of-the-art vector vectors representing Fable 5 nodes
   */
  private seedDefaults() {
    this.documents = [
      {
        id: "VEC-SMC01",
        title: "Smart Money Concepts (SMC) Sweeper",
        category: "strategy",
        // Dimensions: [ProfitFactor, WinRate, Volatility, Drawdown, CapitalLeverage, MarketSentiment, TimeDecay, NeuralRisk]
        vector: [0.85, 0.72, 0.45, 0.12, 0.60, 0.80, 0.30, 0.25],
        metadata: {
          description: "Detects order block sweeps, liquidity runs, and fair value gaps.",
          assetClass: "Crypto/Forex",
          targetTimeframe: "5m/15m",
          profitFactor: 2.8,
          winRate: 72,
          volatility: 45,
          drawdown: 12
        }
      },
      {
        id: "VEC-BBRSI",
        title: "Bollinger Bands + RSI Mean Reversion",
        category: "strategy",
        vector: [0.65, 0.58, 0.30, 0.18, 0.40, 0.50, 0.15, 0.35],
        metadata: {
          description: "Tactical mean-reversion counter-trend rig suited for tight consolidations.",
          assetClass: "Crypto/Equities",
          targetTimeframe: "1h",
          profitFactor: 1.9,
          winRate: 58,
          volatility: 30,
          drawdown: 18
        }
      },
      {
        id: "VEC-TRL02",
        title: "Dynamic Trailing Stop Momentum Rig",
        category: "strategy",
        vector: [0.92, 0.61, 0.85, 0.28, 0.75, 0.90, 0.65, 0.55],
        metadata: {
          description: "Exploits high-volatility breakouts, lock-stepping profit targets with trailing stop vectors.",
          assetClass: "Crypto/EV Equities",
          targetTimeframe: "5m/1h",
          profitFactor: 3.1,
          winRate: 61,
          volatility: 85,
          drawdown: 28
        }
      },
      {
        id: "VEC-OB042",
        title: "Institutional Order Block Swallower",
        category: "pattern",
        vector: [0.78, 0.68, 0.50, 0.14, 0.50, 0.75, 0.20, 0.20],
        metadata: {
          description: "Spots order swallow behaviors where large institutions absorb retail sell orders.",
          assetClass: "Multi-Asset",
          targetTimeframe: "15m/4h",
          profitFactor: 2.4,
          winRate: 68,
          volatility: 50,
          drawdown: 14
        }
      },
      {
        id: "VEC-BRK33",
        title: "Bearish Breakout Trap Safeguard",
        category: "pattern",
        vector: [0.55, 0.52, 0.70, 0.35, 0.30, 0.20, 0.40, 0.80],
        metadata: {
          description: "High stress index structure that triggers when support is swept and quickly reclaimed.",
          assetClass: "Crypto/Indices",
          targetTimeframe: "15m",
          profitFactor: 1.4,
          winRate: 52,
          volatility: 70,
          drawdown: 35
        }
      },
      {
        id: "VEC-NIO45",
        title: "High-Beta EV Electric Vector Rig",
        category: "trade_cluster",
        vector: [0.74, 0.64, 0.78, 0.25, 0.70, 0.85, 0.50, 0.45],
        metadata: {
          description: "Specialized model tuned to capture high volatility momentum in EV stocks like NIO.",
          assetClass: "Equities (NIO)",
          targetTimeframe: "1h/1d",
          profitFactor: 2.3,
          winRate: 64,
          volatility: 78,
          drawdown: 25
        }
      }
    ];
  }
}
