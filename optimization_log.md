# Systemic Optimization Protocol - Log

[SYSTEM]:     ONNX
[TARGET]:     Feature-Drift im Volatilitäts-Regime-Detektor (OHLCV-Heatmap > 3σ Abweichung)
[HYPOTHESIS]: Retraining des Modells reduziert den Prediction Stability Index (PSI) unter den kritischen Schwellenwert und stellt die Konfidenz-Kalibration wieder her.
[IMPLEMENTATION]:
```pine
// Pseudocode Intervention
if onnx_psi > 0.25 or feature_drift_flag:
    synthese_weight_onnx := 0.0
    trigger_retraining(model_id)
```
[METRICS]:    PSI 0.28 → PSI < 0.15
[ROLLBACK-TRIGGER]: Wenn OOS-Accuracy nach Retraining < 60% über 30 Tage, Revert auf vorheriges Modell.
[IMPACT_ON_SYNTHESIS]: Temporäre Reduktion des ONNX-Gewichts auf 0.0 (Veto-Regel). Erhöht proportional die Gewichtung von Loop-Signalen und Orchestrator in der Zwischenzeit.
