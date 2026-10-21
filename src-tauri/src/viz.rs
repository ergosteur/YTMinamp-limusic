//! Spectrum data for the Winamp window's analyzer.
//!
//! mpv plays in-process and libmpv offers no PCM tap, so this records the default output's
//! monitor source through the PulseAudio API (PipeWire's pulse server on modern Linux) and runs
//! Winamp's own FFT on it. Consequence: the bars show everything playing on that output, not just
//! this app. Linux-only; elsewhere the analyzer stays empty. Runs only while the Winamp window is
//! open ([`start`] from `winamp::open`, [`stop`] from `winamp::close`).
//!
//! The FFT and the 75-column frequency mapping are a port of Webamp's (`FFTNullsoft.ts`, itself
//! from Nullsoft's vis_classic, and `VisPainter.ts`'s `paintAnalyzer`), so bar heights match real
//! Winamp. Falloff/peak-hold are per *frame*, so they live in the UI's render loop instead.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use tauri::AppHandle;

pub const EVENT: &str = "winamp-viz";

const RATE: u32 = 44_100;
/// Samples per read: one ~60 Hz frame's worth.
const CHUNK: usize = 735;
const FFT_IN: usize = 1024;
const FFT_OUT: usize = 512;
/// Analyzer columns, before Winamp groups them into 3px bars.
pub const COLUMNS: usize = 75;

static RUNNING: Mutex<Option<Arc<AtomicBool>>> = Mutex::new(None);

/// Start capturing, if not already. Never fails loudly: no audio server just means no bars.
pub fn start(app: &AppHandle) {
    let mut running = RUNNING.lock().unwrap();
    if running.is_some() {
        return;
    }
    let stop = Arc::new(AtomicBool::new(false));
    *running = Some(stop.clone());
    let app = app.clone();
    let _ = std::thread::Builder::new().name("winamp-viz".into()).spawn(move || {
        if let Err(e) = capture(&app, &stop) {
            tracing::warn!(error = %e, "winamp viz: no spectrum (audio capture unavailable)");
        }
    });
}

pub fn stop() {
    if let Some(stop) = RUNNING.lock().unwrap().take() {
        stop.store(true, Ordering::SeqCst);
    }
}

#[cfg(target_os = "linux")]
fn capture(app: &AppHandle, stop: &AtomicBool) -> Result<(), String> {
    use libpulse_binding::def::BufferAttr;
    use libpulse_binding::sample::{Format, Spec};
    use libpulse_binding::stream::Direction;
    use libpulse_simple_binding::Simple;
    use tauri::Emitter;

    let spec = Spec { format: Format::F32le, channels: 1, rate: RATE };
    // Small fragments so a read returns about one frame's worth instead of a big buffer.
    let attr = BufferAttr {
        maxlength: u32::MAX,
        tlength: u32::MAX,
        prebuf: u32::MAX,
        minreq: u32::MAX,
        fragsize: (CHUNK * 4) as u32,
    };
    let pa = Simple::new(
        None,
        "ytminamp",
        Direction::Record,
        Some("@DEFAULT_MONITOR@"),
        "Winamp visualizer",
        &spec,
        None,
        Some(&attr),
    )
    .map_err(|e| format!("{e:?}"))?;

    let fft = Fft::new();
    let mut window = vec![0f32; FFT_IN];
    let mut bytes = vec![0u8; CHUNK * 4];
    while !stop.load(Ordering::SeqCst) {
        pa.read(&mut bytes).map_err(|e| format!("{e:?}"))?;
        window.copy_within(CHUNK.., 0);
        for (dst, src) in window[FFT_IN - CHUNK..].iter_mut().zip(bytes.chunks_exact(4)) {
            *dst = f32::from_le_bytes([src[0], src[1], src[2], src[3]]);
        }
        let _ = app.emit_to(crate::winamp::LABEL, EVENT, fft.columns(&window));
    }
    Ok(())
}

#[cfg(not(target_os = "linux"))]
fn capture(_app: &AppHandle, _stop: &AtomicBool) -> Result<(), String> {
    Err("audio capture is only implemented on Linux".into())
}

/// Nullsoft vis_classic's FFT (via Webamp's `FFTNullsoft.ts`): sine envelope, radix-2 FFT,
/// magnitude equalized on a log10 curve. 1024 samples in, 512 bins out.
struct Fft {
    bitrev: Vec<usize>,
    envelope: Vec<f32>,
    equalize: Vec<f32>,
    cossin: Vec<(f32, f32)>,
}

impl Fft {
    fn new() -> Self {
        let n = FFT_IN;
        let mut bitrev: Vec<usize> = (0..n).collect();
        let mut j = 0;
        for i in 0..n {
            if j > i {
                bitrev.swap(i, j);
            }
            let mut m = n >> 1;
            while m >= 1 && j >= m {
                j -= m;
                m >>= 1;
            }
            j += m;
        }

        let mult = std::f32::consts::TAU / n as f32;
        let envelope =
            (0..n).map(|i| 0.5 + 0.5 * (i as f32 * mult - std::f32::consts::FRAC_PI_2).sin()).collect();

        let mut bias = 0.04f32;
        let equalize = (0..FFT_OUT)
            .map(|i| {
                let inv_half = (9.0 - bias) / FFT_OUT as f32;
                let v = (1.0 + bias + (i as f32 + 1.0) * inv_half).log10();
                bias /= 1.0025;
                v
            })
            .collect();

        let mut cossin = Vec::new();
        let mut size = 2;
        while size <= n {
            let theta = -std::f32::consts::TAU / size as f32;
            cossin.push((theta.cos(), theta.sin()));
            size <<= 1;
        }

        Fft { bitrev, envelope, equalize, cossin }
    }

    /// Samples in [-1, 1] → the 75 analyzer columns Winamp draws (before falloff).
    fn columns(&self, wave: &[f32]) -> Vec<f32> {
        // Webamp feeds the FFT AnalyserNode bytes as (b - 128) / 24, i.e. sample * 128/24.
        const INPUT_SCALE: f32 = 128.0 / 24.0;
        let n = FFT_IN;
        let mut re: Vec<f32> =
            (0..n).map(|i| wave[self.bitrev[i]] * INPUT_SCALE * self.envelope[self.bitrev[i]]).collect();
        let mut im = vec![0f32; n];

        let mut size = 2;
        let mut t = 0;
        while size <= n {
            let (wpr, wpi) = self.cossin[t];
            let (mut wr, mut wi) = (1f32, 0f32);
            let half = size >> 1;
            for m in 0..half {
                let mut i = m;
                while i < n {
                    let j = i + half;
                    let tr = wr * re[j] - wi * im[j];
                    let ti = wr * im[j] + wi * re[j];
                    re[j] = re[i] - tr;
                    im[j] = im[i] - ti;
                    re[i] += tr;
                    im[i] += ti;
                    i += size;
                }
                let wtemp = wr;
                wr = wr * wpr - wi * wpi;
                wi = wi * wpr + wtemp * wpi;
            }
            size <<= 1;
            t += 1;
        }

        let spectrum: Vec<f32> =
            (0..FFT_OUT).map(|i| (re[i] * re[i] + im[i] * im[i]).sqrt() * self.equalize[i]).collect();

        // Webamp's mapping: mostly-logarithmic (scale 0.91) interpolation of 512 bins onto 75.
        const SCALE: f32 = 0.91;
        let log_max = (FFT_OUT as f32).log10();
        (0..COLUMNS)
            .map(|x| {
                let t = x as f32 / (COLUMNS - 1) as f32;
                let linear = t * (FFT_OUT - 1) as f32;
                let log = 10f32.powf(log_max * t);
                let idx = (1.0 - SCALE) * linear + SCALE * log;
                let i1 = (idx.floor() as usize).min(FFT_OUT - 1);
                let i2 = (idx.ceil() as usize).min(FFT_OUT - 1);
                if i1 == i2 {
                    spectrum[i1]
                } else {
                    let f2 = idx - i1 as f32;
                    (1.0 - f2) * spectrum[i1] + f2 * spectrum[i2]
                }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn silence_gives_flat_zero_columns() {
        let cols = Fft::new().columns(&vec![0.0; FFT_IN]);
        assert_eq!(cols.len(), COLUMNS);
        assert!(cols.iter().all(|&c| c == 0.0));
    }

    #[test]
    fn a_low_tone_lights_the_low_columns_more_than_the_high_ones() {
        let wave: Vec<f32> = (0..FFT_IN)
            .map(|i| (i as f32 * 200.0 * std::f32::consts::TAU / RATE as f32).sin() * 0.5)
            .collect();
        let cols = Fft::new().columns(&wave);
        let low: f32 = cols[..20].iter().sum();
        let high: f32 = cols[55..].iter().sum();
        assert!(low > high * 4.0, "low={low} high={high}");
    }
}
