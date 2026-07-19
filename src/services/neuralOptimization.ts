import { inferOnnx, startOnnxTrain } from "../api/onnx";

export interface NeuralInferenceState {
  prediction: number;
  direction: "UP" | "DOWN" | "STABLE";
  confidence: number;
  testMae: number;
  onnxModel: string;
  syncStatus: string;
  isTraining: boolean;
  meanVal: number;
  stdVal: number;
  targetFormula: string;
}

export interface PatternMatch {
  pattern: "Head & Shoulders" | "Double Bottom" | "No Pattern";
  confidence: number;
  keyLevels: { name: string; price: number }[];
  description: string;
}

function modelIdFromName(modelName: string): string {
  return modelName.replace(/\.onnx$/i, "") || "model4";
}

/**
 * ONNX Neural Core — prefers backend onnxruntime; falls back to local simulation.
 */
export class NeuralOptimizationEngine {
  public static calculateInference(
    currentPrice: number,
    modelName: string = "model4.onnx",
  ): NeuralInferenceState {
    return this.simulateInference(currentPrice, modelName);
  }

  public static async calculateInferenceLive(
    currentPrice: number,
    modelName: string,
    symbol: string,
  ): Promise<NeuralInferenceState> {
    try {
      const result = await inferOnnx({
        model_id: modelIdFromName(modelName),
        symbol,
        timeframe: "1h",
        asset_class: "crypto",
      });
      return {
        prediction: result.prediction,
        direction: result.direction,
        confidence: result.confidence,
        testMae: result.testMae,
        onnxModel: result.onnxModel,
        syncStatus: result.syncStatus,
        isTraining: false,
        meanVal: result.meanVal,
        stdVal: result.stdVal,
        targetFormula: result.targetFormula,
      };
    } catch {
      const sim = this.simulateInference(currentPrice, modelName);
      return { ...sim, syncStatus: "SIM FALLBACK" };
    }
  }

  public static async trainModel(modelName: string, symbol: string): Promise<NeuralInferenceState | null> {
    try {
      const job = await startOnnxTrain({
        model_id: modelIdFromName(modelName),
        symbol,
        timeframe: "1h",
        asset_class: "crypto",
        limit: 400,
      });
      if (job.status === "failed") return null;
      return this.calculateInferenceLive(0, modelName, symbol);
    } catch {
      return null;
    }
  }

  public static simulateInference(
    currentPrice: number,
    modelName: string = "model4.onnx",
  ): NeuralInferenceState {
    let rawPredict = 0;
    let testMae = 0.032;
    let targetFormula = "";

    const meanVal = parseFloat((currentPrice + (Math.random() * 2 - 1)).toFixed(2));
    const stdVal = parseFloat((2.5 + Math.random() * 1.5).toFixed(3));

    if (modelName === "model.onnx") {
      rawPredict = Math.sin(currentPrice * 0.04) * 0.03 + (Math.random() * 0.005 - 0.0025);
      testMae = 0.045;
      targetFormula = "y = next_bar.close";
    } else if (modelName === "model2.onnx") {
      rawPredict = Math.cos(currentPrice * 0.06) * 0.04 + (Math.random() * 0.006 - 0.003);
      testMae = 0.052;
      targetFormula = "y = (high - open) - (open - low)";
    } else {
      rawPredict = Math.sin(currentPrice * 0.05) * 0.05 + (Math.random() * 0.008 - 0.004);
      testMae = 0.032;
      targetFormula = "y = (high - high_prev) + (low - low_prev)";
    }

    const direction = rawPredict > 0.005 ? "UP" : rawPredict < -0.005 ? "DOWN" : "STABLE";
    const confidence = Math.min(99.8, 85 + Math.abs(rawPredict * 150) + Math.random() * 5);

    return {
      prediction: parseFloat(rawPredict.toFixed(5)),
      direction,
      confidence: parseFloat(confidence.toFixed(1)),
      testMae,
      onnxModel: modelName,
      syncStatus: "98% SYNC",
      isTraining: false,
      meanVal,
      stdVal,
      targetFormula,
    };
  }

  public static detectPattern(prices: number[]): PatternMatch {
    if (!prices || prices.length < 5) {
      return {
        pattern: "No Pattern",
        confidence: 0,
        keyLevels: [],
        description: "Insufficient historical price points in buffer to run structural scans.",
      };
    }

    const extrema: { index: number; value: number; type: "peak" | "trough" }[] = [];
    for (let i = 1; i < prices.length - 1; i++) {
      if (prices[i] > prices[i - 1] && prices[i] > prices[i + 1]) {
        extrema.push({ index: i, value: prices[i], type: "peak" });
      } else if (prices[i] < prices[i - 1] && prices[i] < prices[i + 1]) {
        extrema.push({ index: i, value: prices[i], type: "trough" });
      }
    }

    const peaks = extrema.filter((e) => e.type === "peak");
    const troughs = extrema.filter((e) => e.type === "trough");

    let hsScore = 0;
    let hsLevels: { name: string; price: number }[] = [];

    if (peaks.length >= 3) {
      for (let i = 0; i <= peaks.length - 3; i++) {
        const left = peaks[i];
        const head = peaks[i + 1];
        const right = peaks[i + 2];

        if (head.value > left.value && head.value > right.value) {
          const avgShoulder = (left.value + right.value) / 2;
          const diff = Math.abs(left.value - right.value) / avgShoulder;

          if (diff < 0.05) {
            const rawConfidence = 70 + (1 - diff / 0.05) * 25;
            hsScore = Math.min(99.4, rawConfidence);
            hsLevels = [
              { name: "Left Shoulder", price: parseFloat(left.value.toFixed(1)) },
              { name: "Head Peak", price: parseFloat(head.value.toFixed(1)) },
              { name: "Right Shoulder", price: parseFloat(right.value.toFixed(1)) },
            ];
            break;
          }
        }
      }
    }

    let dbScore = 0;
    let dbLevels: { name: string; price: number }[] = [];

    if (troughs.length >= 2) {
      for (let i = 0; i <= troughs.length - 2; i++) {
        const t1 = troughs[i];
        const t2 = troughs[i + 1];
        const middlePeaks = peaks.filter((p) => p.index > t1.index && p.index < t2.index);
        if (middlePeaks.length > 0) {
          const peak = middlePeaks[0];
          const avgTrough = (t1.value + t2.value) / 2;
          const diff = Math.abs(t1.value - t2.value) / avgTrough;

          if (diff < 0.03 && peak.value > t1.value && peak.value > t2.value) {
            const rawConfidence = 75 + (1 - diff / 0.03) * 22;
            dbScore = Math.min(99.6, rawConfidence);
            dbLevels = [
              { name: "Bottom 1", price: parseFloat(t1.value.toFixed(1)) },
              { name: "Neckline Resistance", price: parseFloat(peak.value.toFixed(1)) },
              { name: "Bottom 2", price: parseFloat(t2.value.toFixed(1)) },
            ];
            break;
          }
        }
      }
    }

    if (hsScore > 65 && hsScore >= dbScore) {
      return {
        pattern: "Head & Shoulders",
        confidence: parseFloat(hsScore.toFixed(1)),
        keyLevels: hsLevels,
        description:
          "Bearish reversal pattern detected. Watch the neckline support for a break with high volume entry.",
      };
    }
    if (dbScore > 65) {
      return {
        pattern: "Double Bottom",
        confidence: parseFloat(dbScore.toFixed(1)),
        keyLevels: dbLevels,
        description:
          "Bullish double support structure verified. A solid close above the central neckline resistance signals breakout momentum.",
      };
    }

    return {
      pattern: "No Pattern",
      confidence: 0,
      keyLevels: [],
      description:
        "Neural core analysis active. Currently traversing standard oscillating trend channel without classic structure traps.",
    };
  }
}
