/**
 * Fully synthesized Casino and Retro Arcade Audio Engine utilizing standard browser Web Audio API.
 * Synthesizes classic slot spins, poker chips, jackpot wins, and retro alert signals.
 */

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

/**
 * Play a classic slot machine reel tick (short metallic clock click)
 */
export function playSlotTick() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = "sine";
  osc.frequency.setValueAtTime(800, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.05);

  gain.gain.setValueAtTime(0.08, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start();
  osc.stop(ctx.currentTime + 0.06);
}

/**
 * Play a rapid rolling slot machine sequence (simulates reels turning)
 */
export function playReelSpin(durationMs: number = 600) {
  const ctx = getAudioContext();
  if (!ctx) return;

  const ticks = Math.floor(durationMs / 60);
  for (let i = 0; i < ticks; i++) {
    setTimeout(() => {
      playSlotTick();
    }, i * 60);
  }
}

/**
 * Play a poker chip drop sound (short high-frequency impact with a high resonance ring)
 */
export function playChipClick() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const osc1 = ctx.createOscillator();
  const osc2 = ctx.createOscillator();
  const gain = ctx.createGain();

  // Combine high triangle and sine frequencies for plastic contact feel
  osc1.type = "triangle";
  osc1.frequency.setValueAtTime(2200, ctx.currentTime);
  osc1.frequency.exponentialRampToValueAtTime(1600, ctx.currentTime + 0.04);

  osc2.type = "sine";
  osc2.frequency.setValueAtTime(3400, ctx.currentTime);
  osc2.frequency.exponentialRampToValueAtTime(2800, ctx.currentTime + 0.03);

  gain.gain.setValueAtTime(0.12, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);

  osc1.connect(gain);
  osc2.connect(gain);
  gain.connect(ctx.destination);

  osc1.start();
  osc2.start();
  osc1.stop(ctx.currentTime + 0.05);
  osc2.stop(ctx.currentTime + 0.05);
}

/**
 * Play multiple poker chips stacking/shuffling together
 */
export function playChipStack() {
  for (let i = 0; i < 4; i++) {
    setTimeout(() => {
      playChipClick();
    }, i * 75);
  }
}

/**
 * Play a retro high-pitched casino slot jackpot arpeggio (The "Win" Sound)
 */
export function playJackpotBell() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const notes = [523.25, 659.25, 783.99, 1046.50, 1318.51, 1567.98]; // C5, E5, G5, C6, E6, G6
  const duration = 0.12;

  notes.forEach((freq, idx) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const startTime = ctx.currentTime + idx * 0.08;

    osc.type = "square"; // Authentic 8-bit chip sound
    osc.frequency.setValueAtTime(freq, startTime);
    
    // Add frequency vibrato
    osc.frequency.linearRampToValueAtTime(freq + 15, startTime + duration);

    gain.gain.setValueAtTime(0.1, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(startTime);
    osc.stop(startTime + duration);
  });
}

/**
 * Play a retro failure / trap warning buzzer (Descending 8-bit notes)
 */
export function playBuzzerWarning() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const notes = [293.66, 246.94, 196.00]; // D4, B3, G3
  const duration = 0.15;

  notes.forEach((freq, idx) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const startTime = ctx.currentTime + idx * 0.12;

    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(freq, startTime);
    osc.frequency.linearRampToValueAtTime(freq - 10, startTime + duration);

    gain.gain.setValueAtTime(0.15, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(startTime);
    osc.stop(startTime + duration);
  });
}

/**
 * Play a classic coin insert / cascading token drop sweep
 */
export function playCascadingCoins() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const count = 12;
  for (let i = 0; i < count; i++) {
    const timeOffset = i * 45;
    setTimeout(() => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      
      // Ringing high metallic pitches
      const pitch = 2000 + Math.random() * 2500;
      osc.type = "triangle";
      osc.frequency.setValueAtTime(pitch, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(pitch - 800, ctx.currentTime + 0.08);

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.09);
    }, timeOffset);
  }
}


/**
 * Play a custom synthesized high-energy laser sound effect for a profitable trade (Kill).
 */
export function playKillSound() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const osc1 = ctx.createOscillator();
  const osc2 = ctx.createOscillator();
  const gain = ctx.createGain();

  osc1.type = "sine";
  osc1.frequency.setValueAtTime(440, ctx.currentTime);
  osc1.frequency.exponentialRampToValueAtTime(1400, ctx.currentTime + 0.15);

  osc2.type = "triangle";
  osc2.frequency.setValueAtTime(554.37, ctx.currentTime); // C#
  osc2.frequency.exponentialRampToValueAtTime(1760, ctx.currentTime + 0.12);

  gain.gain.setValueAtTime(0.12, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);

  osc1.connect(gain);
  osc2.connect(gain);
  gain.connect(ctx.destination);

  osc1.start();
  osc2.start();
  osc1.stop(ctx.currentTime + 0.18);
  osc2.stop(ctx.currentTime + 0.18);
}

/**
 * Play a custom synthesized heavy low drop crash sound for a lost trade (Death).
 */
export function playDeathSound() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(220, ctx.currentTime);
  osc.frequency.linearRampToValueAtTime(55, ctx.currentTime + 0.3);

  gain.gain.setValueAtTime(0.15, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.setValueAtTime(300, ctx.currentTime);
  filter.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.3);

  osc.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);

  osc.start();
  osc.stop(ctx.currentTime + 0.35);
}

/**
 * Play a wacky, slide-whistle descending frequency and clown horn "humiliation" sound.
 */
export function playHumiliationSound() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const time = ctx.currentTime;

  const osc1 = ctx.createOscillator();
  const gain1 = ctx.createGain();
  osc1.type = "triangle";
  osc1.frequency.setValueAtTime(800, time);
  osc1.frequency.linearRampToValueAtTime(150, time + 0.35);

  gain1.gain.setValueAtTime(0.15, time);
  gain1.gain.exponentialRampToValueAtTime(0.001, time + 0.35);

  osc1.connect(gain1);
  gain1.connect(ctx.destination);
  osc1.start(time);
  osc1.stop(time + 0.35);

  setTimeout(() => {
    const ctx2 = getAudioContext();
    if (!ctx2) return;
    const t2 = ctx2.currentTime;

    const osc2 = ctx2.createOscillator();
    const osc3 = ctx2.createOscillator();
    const gain2 = ctx2.createGain();

    osc2.type = "square";
    osc2.frequency.setValueAtTime(110, t2);
    
    osc3.type = "square";
    osc3.frequency.setValueAtTime(113, t2);

    gain2.gain.setValueAtTime(0.18, t2);
    gain2.gain.exponentialRampToValueAtTime(0.001, t2 + 0.4);

    const bpf = ctx2.createBiquadFilter();
    bpf.type = "bandpass";
    bpf.frequency.setValueAtTime(400, t2);

    osc2.connect(bpf);
    osc3.connect(bpf);
    bpf.connect(gain2);
    gain2.connect(ctx2.destination);

    osc2.start(t2);
    osc3.start(t2);
    osc2.stop(t2 + 0.4);
    osc3.stop(t2 + 0.4);
  }, 300);
}

/**
 * Play a dark, aggressive sci-fi cinematic low bass drop for Nemesis events.
 */
export function playNemesisSound() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const time = ctx.currentTime;

  const osc1 = ctx.createOscillator();
  const osc2 = ctx.createOscillator();
  const filter = ctx.createBiquadFilter();
  const gain = ctx.createGain();

  osc1.type = "sawtooth";
  osc1.frequency.setValueAtTime(65.41, time); // C2
  osc1.frequency.linearRampToValueAtTime(48.99, time + 0.7); // Descend to G1

  osc2.type = "square";
  osc2.frequency.setValueAtTime(65.8, time); // Detuned C2
  osc2.frequency.linearRampToValueAtTime(49.3, time + 0.7);

  filter.type = "lowpass";
  filter.Q.setValueAtTime(8, time);
  filter.frequency.setValueAtTime(120, time);
  filter.frequency.exponentialRampToValueAtTime(450, time + 0.2);
  filter.frequency.exponentialRampToValueAtTime(60, time + 0.7);

  gain.gain.setValueAtTime(0.25, time);
  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.85);

  osc1.connect(filter);
  osc2.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);

  osc1.start(time);
  osc2.start(time);
  osc1.stop(time + 0.85);
  osc2.stop(time + 0.85);
}

/**
 * Play a gorgeous shower of cascade arpeggios, jackpot rings, and golden synth rises.
 */
export function playWolfOfWallStreetSound() {
  const ctx = getAudioContext();
  if (!ctx) return;

  const time = ctx.currentTime;

  const notes = [261.63, 329.63, 392.00, 523.25, 659.25, 783.99, 1046.50, 1318.51, 1567.98, 2093.00]; // C4 to C7
  notes.forEach((freq, idx) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const noteTime = time + idx * 0.06;

    osc.type = "triangle";
    osc.frequency.setValueAtTime(freq, noteTime);
    osc.frequency.exponentialRampToValueAtTime(freq * 1.05, noteTime + 0.08);

    gain.gain.setValueAtTime(0.1, noteTime);
    gain.gain.exponentialRampToValueAtTime(0.001, noteTime + 0.1);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(noteTime);
    osc.stop(noteTime + 0.1);
  });

  setTimeout(() => {
    const ctx2 = getAudioContext();
    if (!ctx2) return;
    const t2 = ctx2.currentTime;

    for (let i = 0; i < 3; i++) {
      const start = t2 + i * 0.15;
      const osc = ctx2.createOscillator();
      const gain = ctx2.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(1000 + i * 200, start);
      osc.frequency.exponentialRampToValueAtTime(3000 + i * 300, start + 0.25);

      gain.gain.setValueAtTime(0.08, start);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.25);

      osc.connect(gain);
      gain.connect(ctx2.destination);

      osc.start(start);
      osc.stop(start + 0.25);
    }
  }, 350);

  // Play jackpot bells in rapid succession
  setTimeout(() => {
    playJackpotBell();
  }, 100);
  setTimeout(() => {
    playJackpotBell();
  }, 400);
}

/**
 * Play a badass Heroes of Newerth voice-pack announcer call based on P&L, streak data, and premium scenarios.
 */
export function announceTradeOutcome(
  pnl: number,
  streak: { wins: number; losses: number },
  language: "en" | "de" = "en",
  options?: { isNemesis?: boolean; isInstantBackfire?: boolean; symbol?: string }
) {
  if (typeof window === "undefined") return "";

  const isNemesis = options?.isNemesis;
  const isInstantBackfire = options?.isInstantBackfire;
  const isWolfOfWallStreet = streak.wins === 15 || streak.wins >= 15;
  const symbol = options?.symbol || "";

  // 1. Play premium, high-fidelity Web Audio synthesis sound effects
  if (isWolfOfWallStreet) {
    playWolfOfWallStreetSound();
  } else if (isNemesis) {
    playNemesisSound();
  } else if (isInstantBackfire) {
    playHumiliationSound();
  } else if (pnl > 0) {
    playKillSound();
  } else if (pnl < 0) {
    playDeathSound();
  } else {
    playChipClick();
  }

  // 2. Select the HoN Badass Announcer voice line
  let voiceLine = "";

  if (language === "de") {
    if (isWolfOfWallStreet) {
      voiceLine = "Der Wolf der Wall Street! Unsterbliche Fünfzehn-Gewinnsträhne!";
    } else if (isNemesis) {
      voiceLine = `Erzfeind! Drei Verluste in Folge bei ${symbol || "diesem Asset"}!`;
    } else if (isInstantBackfire) {
      voiceLine = "Erniedrigung! Der Markt hat dich eiskalt erwischt!";
    } else if (pnl > 0) {
      if (streak.wins === 1) {
        voiceLine = "Erstes Blut! Kirschenpflücker!";
      } else if (streak.wins === 2) {
        voiceLine = "Doppel-Kill!";
      } else if (streak.wins === 3) {
        voiceLine = "Blutbad!";
      } else if (streak.wins === 4) {
        voiceLine = "Dominierend!";
      } else if (streak.wins === 5) {
        voiceLine = "Unaufhaltsam!";
      } else if (streak.wins === 6) {
        voiceLine = "Kaltblütiger Mord!";
      } else if (streak.wins === 7) {
        voiceLine = "Unsterblich!";
      } else if (streak.wins === 8) {
        voiceLine = "Legendär!";
      } else if (streak.wins === 9) {
        voiceLine = "Dschingis Khan!";
      } else if (streak.wins >= 10) {
        voiceLine = "Vernichtung! Du bist ein absoluter Teufelskerl!";
      } else {
        const genericKills = ["Niedergestreckt!", "Hol dir das!", "Friss das!", "Booyah!"];
        voiceLine = genericKills[Math.floor(Math.random() * genericKills.length)];
      }
    } else if (pnl < 0) {
      if (streak.losses === 1) {
        voiceLine = "Zerstört!";
      } else if (streak.losses === 2) {
        voiceLine = "Verweigert!";
      } else if (streak.losses >= 3) {
        voiceLine = "Erniedrigung! Wutanfall!";
      } else {
        const genericDeaths = ["Besiegt!", "Du wurdest zerlegt!", "Wutausbruch!", "Zerstört!"];
        voiceLine = genericDeaths[Math.floor(Math.random() * genericDeaths.length)];
      }
    } else {
      const assistLines = ["Unterstützung!", "Retter!", "Helfende Hand!", "Teamwork!"];
      voiceLine = assistLines[Math.floor(Math.random() * assistLines.length)];
    }
  } else {
    // English (Default)
    if (isWolfOfWallStreet) {
      voiceLine = "The Wolf of Wall Street! Immortal fifteen-win streak!";
    } else if (isNemesis) {
      voiceLine = `Nemesis! Three consecutive losses on ${symbol || "this asset"}!`;
    } else if (isInstantBackfire) {
      voiceLine = "Humiliation! Market instantly backfired on you!";
    } else if (pnl > 0) {
      if (streak.wins === 1) {
        voiceLine = "Cherry Popper!"; // First blood
      } else if (streak.wins === 2) {
        voiceLine = "Double Kill!";
      } else if (streak.wins === 3) {
        voiceLine = "Blood Bath!";
      } else if (streak.wins === 4) {
        voiceLine = "Dominating!";
      } else if (streak.wins === 5) {
        voiceLine = "Unstoppable!";
      } else if (streak.wins === 6) {
        voiceLine = "Bloody Murder!";
      } else if (streak.wins === 7) {
        voiceLine = "Immortal!";
      } else if (streak.wins === 8) {
        voiceLine = "Legendary!";
      } else if (streak.wins === 9) {
        voiceLine = "Genghis Khan!";
      } else if (streak.wins >= 10) {
        voiceLine = "Annihilation! You are a badass!";
      } else {
        const genericKills = ["Smackdown!", "Get some!", "Eat that!", "Booyah!"];
        voiceLine = genericKills[Math.floor(Math.random() * genericKills.length)];
      }
    } else if (pnl < 0) {
      if (streak.losses === 1) {
        voiceLine = "Owned!";
      } else if (streak.losses === 2) {
        voiceLine = "Denied!";
      } else if (streak.losses >= 3) {
        voiceLine = "Humiliation! Rage quit!";
      } else {
        const genericDeaths = ["Defeated!", "You got wrecked!", "Rage quit!", "Owned!"];
        voiceLine = genericDeaths[Math.floor(Math.random() * genericDeaths.length)];
      }
    } else {
      const assistLines = ["Assist!", "Savior!", "Helping hand!", "Teamwork!"];
      voiceLine = assistLines[Math.floor(Math.random() * assistLines.length)];
    }
  }

  // 3. Synthesize the announcement with a deep, dramatic announcer voice
  try {
    const synth = window.speechSynthesis;
    if (synth) {
      synth.cancel();

      const utterance = new SpeechSynthesisUtterance(voiceLine);
      const voices = synth.getVoices();
      
      let voice;
      if (language === "de") {
        voice = voices.find(v => 
          v.lang.includes("de-DE") && 
          (v.name.toLowerCase().includes("google") || 
           v.name.toLowerCase().includes("male") || 
           v.name.toLowerCase().includes("premium"))
        ) || voices.find(v => v.lang.startsWith("de"));
      } else {
        voice = voices.find(v => 
          v.lang.includes("en-US") && 
          (v.name.toLowerCase().includes("natural") || 
           v.name.toLowerCase().includes("google") || 
           v.name.toLowerCase().includes("male") || 
           v.name.toLowerCase().includes("premium"))
        ) || voices.find(v => v.lang.startsWith("en"));
      }

      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      } else if (language === "de") {
        utterance.lang = "de-DE";
      } else {
        utterance.lang = "en-US";
      }

      // Deep voice effect
      utterance.pitch = language === "de" ? 0.6 : 0.5;
      utterance.rate = 0.85;
      utterance.volume = 1.0;

      synth.speak(utterance);
    }
  } catch (err) {
    console.warn("Speech synthesis failed or was interrupted:", err);
  }

  return voiceLine;
}


