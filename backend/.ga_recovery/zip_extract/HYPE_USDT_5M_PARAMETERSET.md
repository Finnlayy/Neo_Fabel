# HYPE/USDT 5m Parameter-Optimierung

Diese Voreinstellung ist fuer `HYPE/USDT` auf `5 Minuten` bewusst strenger als die ETH-Version, weil das Paar typischerweise volatiler und noisiger handelt.

## Empfohlene Defaults

- `Contracts`: `2`
- `Min. Confidence Score`: `80`
- `SL ATR Multiplikator`: `1.6`
- `TP ATR Multiplikator`: `5.2`
- `Volumen Multiplikator`: `1.6`
- `Max Tagesbewegung Prozent`: `9.0`
- `Session Filter aktivieren`: `false`
- `Trading Session (UTC)`: `0000-2359`
- `Short Signale aktivieren`: `true`

## Warum diese Werte

- Hoeherer `min_conf`, damit auf 5m weniger schwache Breakouts durchkommen.
- Hoeherer `sl_atr_mul`, damit normale HYPE-Schwankungen nicht sofort ausstoppen.
- Hoeherer `tp_atr_mul`, damit der Reward bei impulsiven Trendphasen intakt bleibt.
- Hoeherer `vol_mult`, damit Signale nur bei klar ueberdurchschnittlichem Volumen feuern.
- Hoeherer `max_daily_move_pct`, weil HYPE haeufig groessere Intraday-Bewegungen macht als ETH.

## Datei

Verwende fuer dieses Preset:

- `HYPE_USDT_GlintNews_PionexBot_5m.pine`
