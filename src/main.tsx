import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import {AuthProvider} from './auth/AuthProvider';
import {redirectLoopbackIpToLocalhost} from './auth/firebase';
import './index.css';

// Firebase authorized domain is localhost, not 127.0.0.1 — bounce before auth UI mounts.
const skipReactMount = redirectLoopbackIpToLocalhost();

// Intercept performance.measure and performance.mark to prevent DataCloneError in iframe-based sandboxes
if (typeof window !== 'undefined' && window.performance) {
  const perf = window.performance;

  if (perf.measure) {
    const originalMeasure = perf.measure;
    perf.measure = function (
      measureName: string,
      startOrMeasureOptions?: any,
      endMark?: string
    ) {
      try {
        if (typeof startOrMeasureOptions === 'object' && startOrMeasureOptions !== null) {
          const safeOptions: any = {};
          for (const key of Object.keys(startOrMeasureOptions)) {
            const val = startOrMeasureOptions[key];
            if (typeof val === 'function' || typeof val === 'symbol') {
              continue;
            }
            if (key === 'detail') {
              try {
                if (typeof structuredClone === 'function') {
                  structuredClone(val);
                  safeOptions[key] = val;
                } else {
                  safeOptions[key] = JSON.parse(JSON.stringify(val));
                }
              } catch {
                try {
                  safeOptions[key] = JSON.parse(JSON.stringify(val));
                } catch {
                  safeOptions[key] = String(val);
                }
              }
            } else {
              safeOptions[key] = val;
            }
          }
          return originalMeasure.call(perf, measureName, safeOptions, endMark);
        }
        return originalMeasure.call(perf, measureName, startOrMeasureOptions, endMark);
      } catch (err) {
        console.warn('[Performance Override] Caught and handled error in performance.measure:', err);
        try {
          return originalMeasure.call(perf, measureName);
        } catch {
          return null as any;
        }
      }
    };
  }

  if (perf.mark) {
    const originalMark = perf.mark;
    perf.mark = function (markName: string, markOptions?: any) {
      try {
        if (typeof markOptions === 'object' && markOptions !== null) {
          const safeOptions: any = {};
          for (const key of Object.keys(markOptions)) {
            const val = markOptions[key];
            if (typeof val === 'function' || typeof val === 'symbol') {
              continue;
            }
            if (key === 'detail') {
              try {
                if (typeof structuredClone === 'function') {
                  structuredClone(val);
                  safeOptions[key] = val;
                } else {
                  safeOptions[key] = JSON.parse(JSON.stringify(val));
                }
              } catch {
                try {
                  safeOptions[key] = JSON.parse(JSON.stringify(val));
                } catch {
                  safeOptions[key] = String(val);
                }
              }
            } else {
              safeOptions[key] = val;
            }
          }
          return originalMark.call(perf, markName, safeOptions);
        }
        return originalMark.call(perf, markName, markOptions);
      } catch (err) {
        console.warn('[Performance Override] Caught and handled error in performance.mark:', err);
        try {
          return originalMark.call(perf, markName);
        } catch {
          return null as any;
        }
      }
    };
  }
}

if (!skipReactMount) {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <AuthProvider>
        <App />
      </AuthProvider>
    </StrictMode>,
  );
}

