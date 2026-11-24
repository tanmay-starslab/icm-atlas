// CLOUDY c17.03 (FG11 UVB, GASS10 solar abundances) line emissivity surface brightness engine.
// Lazy-loaded ONLY when Emission (SB) mode is activated so the first-frame shell budget stays untouched.
// Computes 3D log10(epsilon [erg s^-1 cm^-3]) cubes via trilinear interpolation over (nH, Z, T)
// and projects exact physical surface brightness log10(SB [erg s^-1 cm^-2 arcsec^-2]).

export const EPS_MIN = -48.0;
export const EPS_MAX = -12.0;
export const EPS_REF = -25.0;
export const LOG10_CM_PER_KPC = 21.4893505383;
export const LOG10_4PI_ARCSEC2 = 11.7280614585;
export const DEFAULT_LINE = "OVIII_18.97";

export const CLOUDY_LINES = Object.freeze([
  {idx: 0,  id: "Ha_6563",     label: "Hα 6563 Å",         short: "Hα",      wave_A: 6562.81, band: "Optical", sb_range: [-21.5, -14.5], tex: "\\mathrm{H}\\alpha\\ 6563\\,\\mathrm{\\AA}"},
  {idx: 1,  id: "Lya_1216",    label: "Lyα 1216 Å",        short: "Lyα",     wave_A: 1215.67, band: "FUV",     sb_range: [-21.0, -14.0], tex: "\\mathrm{Ly}\\alpha\\ 1216\\,\\mathrm{\\AA}"},
  {idx: 2,  id: "OII_3727",    label: "[O II] 3727/29 Å",  short: "[O II]",  wave_A: 3727.42, band: "Optical", sb_range: [-22.0, -15.0], tex: "[\\mathrm{O\\,II}]\\ 3727/29\\,\\mathrm{\\AA}"},
  {idx: 3,  id: "OIII_5007",   label: "[O III] 5007 Å",    short: "[O III]", wave_A: 5006.84, band: "Optical", sb_range: [-22.0, -15.0], tex: "[\\mathrm{O\\,III}]\\ 5007\\,\\mathrm{\\AA}"},
  {idx: 4,  id: "NII_6583",    label: "[N II] 6583 Å",     short: "[N II]",  wave_A: 6583.45, band: "Optical", sb_range: [-22.5, -15.5], tex: "[\\mathrm{N\\,II}]\\ 6583\\,\\mathrm{\\AA}"},
  {idx: 5,  id: "MgII_2798",   label: "Mg II 2796/03 Å",   short: "Mg II",   wave_A: 2798.0,  band: "NUV",     sb_range: [-22.5, -15.5], tex: "\\mathrm{Mg\\,II}\\ 2796/03\\,\\mathrm{\\AA}"},
  {idx: 6,  id: "CIII_977",    label: "C III 977 Å",       short: "C III",   wave_A: 977.02,  band: "FUV",     sb_range: [-22.5, -16.0], tex: "\\mathrm{C\\,III}\\ 977\\,\\mathrm{\\AA}"},
  {idx: 7,  id: "CIV_1548",    label: "C IV 1548/51 Å",    short: "C IV",    wave_A: 1549.06, band: "FUV",     sb_range: [-23.0, -16.5], tex: "\\mathrm{C\\,IV}\\ 1548/51\\,\\mathrm{\\AA}"},
  {idx: 8,  id: "OVI_1032",    label: "O VI 1032/38 Å",    short: "O VI",    wave_A: 1033.82, band: "FUV",     sb_range: [-23.0, -16.5], tex: "\\mathrm{O\\,VI}\\ 1032/38\\,\\mathrm{\\AA}"},
  {idx: 9,  id: "OVII_21.6",   label: "O VII 21.6 Å",      short: "O VII",   wave_A: 21.602,  band: "X-ray",   sb_range: [-24.0, -17.5], tex: "\\mathrm{O\\,VII}\\ 21.6\\,\\mathrm{\\AA}"},
  {idx: 10, id: "OVIII_18.97", label: "O VIII 18.97 Å",    short: "O VIII",  wave_A: 18.971,  band: "X-ray",   sb_range: [-24.0, -17.0], tex: "\\mathrm{O\\,VIII}\\ 18.97\\,\\mathrm{\\AA}"},
  {idx: 11, id: "FeXXV_1.85",  label: "Fe XXV 1.85 Å",     short: "Fe XXV",  wave_A: 1.8504,  band: "X-ray",   sb_range: [-24.5, -16.5], tex: "\\mathrm{Fe\\,XXV}\\ 1.85\\,\\mathrm{\\AA}"},
]);

export const CLOUDY_LINE_GROUPS = Object.freeze([
  {label: "X-ray (ICM)", ids: ["OVIII_18.97", "FeXXV_1.85", "OVII_21.6"]},
  {label: "Optical (Cool Core)", ids: ["Ha_6563", "OII_3727", "OIII_5007", "NII_6583"]},
  {label: "UV (Warm-Hot / CGM)", ids: ["OVI_1032", "CIV_1548", "CIII_977", "MgII_2798", "Lya_1216"]},
]);

export function getCloudyLine(id) {
  return CLOUDY_LINES.find(l => l.id === id) || CLOUDY_LINES.find(l => l.id === DEFAULT_LINE);
}

let cachedLutP = null;

export function loadCloudyLut({
  binUrl = "data/cloudy_emissivity_z0.bin",
  metaUrl = "data/cloudy_emissivity_meta.json",
  fetchFn = null,
  force = false,
} = {}) {
  if (!force && cachedLutP && !fetchFn) return cachedLutP;
  const doFetch = fetchFn || ((u) => fetch(u));
  const p = (async () => {
    const [rMeta, rBin] = await Promise.all([doFetch(metaUrl), doFetch(binUrl)]);
    if (!rMeta.ok) throw new Error(`CLOUDY meta HTTP ${rMeta.status}`);
    if (!rBin.ok) throw new Error(`CLOUDY LUT HTTP ${rBin.status}`);
    const [meta, buf] = await Promise.all([rMeta.json(), rBin.arrayBuffer()]);
    const data = new Uint8Array(buf);
    const [nL, nN, nZ, nT] = meta.shape;
    const expected = nL * nN * nZ * nT;
    if (data.length !== expected) throw new Error(`CLOUDY LUT size ${data.length} != expected ${expected}`);
    return {meta, data, lines: CLOUDY_LINES};
  })();
  if (!fetchFn) {
    cachedLutP = p;
    p.catch(() => { if (cachedLutP === p) cachedLutP = null; });
  }
  return p;
}

/**
 * Trilinearly interpolate log10(epsilon [erg s^-1 cm^-3]) from the CLOUDY c17.03 LUT
 * for a single (log10 nH [cm^-3], log10 Z [Z_sun], log10 T [K]) point.
 */
export function interpLogEps(lut, lineId, logNH, logZ, logT) {
  const {meta, data} = lut;
  const line = typeof lineId === "number" ? CLOUDY_LINES[lineId] : getCloudyLine(lineId);
  const idx = line ? line.idx : 10;
  const nN = meta.nH_len, nZ = meta.Z_len, nT = meta.T_len;
  const uN = Math.max(0, Math.min(nN - 1, (logNH - meta.nH_min) / (meta.nH_max - meta.nH_min) * (nN - 1)));
  const uZ = Math.max(0, Math.min(nZ - 1, (logZ  - meta.Z_min)  / (meta.Z_max  - meta.Z_min)  * (nZ - 1)));
  const uT = Math.max(0, Math.min(nT - 1, (logT  - meta.T_min)  / (meta.T_max  - meta.T_min)  * (nT - 1)));
  const i0 = Math.min(nN - 2, Math.floor(uN)), i1 = i0 + 1, fN = uN - i0;
  const j0 = Math.min(nZ - 2, Math.floor(uZ)), j1 = j0 + 1, fZ = uZ - j0;
  const k0 = Math.min(nT - 2, Math.floor(uT)), k1 = k0 + 1, fT = uT - k0;
  const base = idx * nN * nZ * nT;
  const sN = nZ * nT;
  const o00 = base + i0 * sN + j0 * nT, o01 = base + i0 * sN + j1 * nT;
  const o10 = base + i1 * sN + j0 * nT, o11 = base + i1 * sN + j1 * nT;
  const c00 = data[o00 + k0] * (1 - fT) + data[o00 + k1] * fT;
  const c01 = data[o01 + k0] * (1 - fT) + data[o01 + k1] * fT;
  const c10 = data[o10 + k0] * (1 - fT) + data[o10 + k1] * fT;
  const c11 = data[o11 + k0] * (1 - fT) + data[o11 + k1] * fT;
  const c0 = c00 * (1 - fZ) + c01 * fZ;
  const c1 = c10 * (1 - fZ) + c11 * fZ;
  const qInterp = c0 * (1 - fN) + c1 * fN;
  const emin = meta.eps_min ?? EPS_MIN, emax = meta.eps_max ?? EPS_MAX;
  return emin + (qInterp / 255.0) * (emax - emin);
}

/**
 * Compute a 3D log10(epsilon [erg s^-1 cm^-3]) cube quantized to uint8 on [EPS_MIN, EPS_MAX]
 * (q = 0 empty, q = 1..255 linear in [-48.0, -12.0]) from loaded nH, T, and optional Z uint8 cubes.
 */
export function computeEmissivityCube(lut, lineId, inp, ranges) {
  const {meta, data} = lut;
  const qN = inp.nH, qT = inp.T, qZ = inp.Z || null;
  if (!qN || !qT) throw new Error("computeEmissivityCube: requires nH and T cubes");
  const N = qN.length;
  const out = new Uint8Array(N);
  const line = typeof lineId === "number" ? CLOUDY_LINES[lineId] : getCloudyLine(lineId);
  const idx = line ? line.idx : 10;
  const nN = meta.nH_len, nZ = meta.Z_len, nT = meta.T_len;
  const sN = nZ * nT;
  const base = idx * nN * sN;

  // Precompute 256-entry axis index + fraction tables for zero-division inner loop
  const i0N = new Int32Array(256), i1N = new Int32Array(256), fNA = new Float32Array(256);
  const j0Z = new Int32Array(256), j1Z = new Int32Array(256), fZA = new Float32Array(256);
  const k0T = new Int32Array(256), k1T = new Int32Array(256), fTA = new Float32Array(256);

  const prepAxis = (r, axMin, axMax, axLen, i0A, i1A, fA, stride, fallbackVal) => {
    const invSpan = (axLen - 1) / (axMax - axMin);
    const fill = (q, lv) => {
      const u = Math.max(0, Math.min(axLen - 1, (lv - axMin) * invSpan));
      const i0 = Math.min(axLen - 2, Math.floor(u));
      i0A[q] = i0 * stride;
      i1A[q] = (i0 + 1) * stride;
      fA[q] = u - i0;
    };
    fill(0, fallbackVal);
    if (r) {
      const step = (r[1] - r[0]) / 254.0;
      for (let q = 1; q < 256; q++) fill(q, r[0] + (q - 1) * step);
    } else {
      for (let q = 1; q < 256; q++) fill(q, fallbackVal);
    }
  };

  prepAxis(ranges.nH, meta.nH_min, meta.nH_max, nN, i0N, i1N, fNA, sN, -7.0);
  prepAxis(ranges.Z,  meta.Z_min,  meta.Z_max,  nZ, j0Z, j1Z, fZA, nT, -0.5228787); // 0.3 Z_sun ICM default
  prepAxis(ranges.T,  meta.T_min,  meta.T_max,  nT, k0T, k1T, fTA, 1,   7.0);

  const emin = meta.eps_min ?? EPS_MIN, emax = meta.eps_max ?? EPS_MAX;
  const qScale = ((emax - emin) / (EPS_MAX - EPS_MIN)) * (254.0 / 255.0);
  const qOffset = 1.0 + ((emin - EPS_MIN) / (EPS_MAX - EPS_MIN)) * 254.0;

  if (qZ) {
    for (let i = 0; i < N; i++) {
      const a = qN[i], b = qT[i];
      if (!a || !b) continue;
      const c = qZ[i];
      const n0 = base + i0N[a], n1 = base + i1N[a], fn = fNA[a];
      const z0 = j0Z[c], z1 = j1Z[c], fz = fZA[c];
      const t0 = k0T[b], t1 = k1T[b], ft = fTA[b], mt = 1.0 - ft;
      const o00 = n0 + z0, o01 = n0 + z1, o10 = n1 + z0, o11 = n1 + z1;
      const c00 = data[o00 + t0] * mt + data[o00 + t1] * ft;
      const c01 = data[o01 + t0] * mt + data[o01 + t1] * ft;
      const c10 = data[o10 + t0] * mt + data[o10 + t1] * ft;
      const c11 = data[o11 + t0] * mt + data[o11 + t1] * ft;
      const qInterp = (c00 + (c01 - c00) * fz) * (1.0 - fn) + (c10 + (c11 - c10) * fz) * fn;
      const qOut = Math.round(qOffset + qInterp * qScale);
      out[i] = qOut < 1 ? 1 : qOut > 255 ? 255 : qOut;
    }
  } else {
    const z0 = j0Z[0], z1 = j1Z[0], fz = fZA[0];
    for (let i = 0; i < N; i++) {
      const a = qN[i], b = qT[i];
      if (!a || !b) continue;
      const n0 = base + i0N[a], n1 = base + i1N[a], fn = fNA[a];
      const t0 = k0T[b], t1 = k1T[b], ft = fTA[b], mt = 1.0 - ft;
      const o00 = n0 + z0, o01 = n0 + z1, o10 = n1 + z0, o11 = n1 + z1;
      const c00 = data[o00 + t0] * mt + data[o00 + t1] * ft;
      const c01 = data[o01 + t0] * mt + data[o01 + t1] * ft;
      const c10 = data[o10 + t0] * mt + data[o10 + t1] * ft;
      const c11 = data[o11 + t0] * mt + data[o11 + t1] * ft;
      const qInterp = (c00 + (c01 - c00) * fz) * (1.0 - fn) + (c10 + (c11 - c10) * fz) * fn;
      const qOut = Math.round(qOffset + qInterp * qScale);
      out[i] = qOut < 1 ? 1 : qOut > 255 ? 255 : qOut;
    }
  }
  return out;
}

/**
 * Exact physical surface brightness log10(SB [erg s^-1 cm^-2 arcsec^-2]) from
 * shifted ray integral sum(10^(logEps - EPS_REF) * ds_kpc).
 */
export function log10SBFromIntegral(sumShiftedKpc, redshift = 0.0) {
  if (!(sumShiftedKpc > 0)) return -Infinity;
  return EPS_REF + Math.log10(sumShiftedKpc) + LOG10_CM_PER_KPC - LOG10_4PI_ARCSEC2 - 4.0 * Math.log10(1.0 + Math.max(0.0, redshift));
}
