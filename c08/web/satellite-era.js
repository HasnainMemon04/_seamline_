// Launch eligibility is separate from FIRMS coverage. See docs/SATELLITE_VISUALS.md.
(function (root) {
  'use strict';
  const launches = { Terra: '1999-12-18', Aqua: '2002-05-04', SNPP: '2011-10-28', NOAA20: '2017-11-18', NOAA21: '2022-11-10' };
  function dateFor(month, day = 0) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month || '')) return null;
    const [y, m] = month.split('-').map(Number), last = new Date(Date.UTC(y, m, 0)).getUTCDate();
    return `${month}-${String(day > 0 ? Math.min(last, Math.max(1, day)) : last).padStart(2, '0')}`;
  }
  function visible(key, month, day = 0) {
    const date = dateFor(month, day);
    return !!date && !!launches[key] && date >= launches[key];
  }
  function periodSeconds(altKm) { return 2 * Math.PI * Math.sqrt(Math.pow(6371.0088 + altKm, 3) / 398600.4418); }
  // A smooth clock: no modulo before multiplying different satellite periods.
  function phase(sat, elapsedSeconds) { return (sat.phase0 + elapsedSeconds * 20 * 360 / periodSeconds(sat.altKm)) % 360; }
  const api = { launches, dateFor, visible, phase, periodSeconds, speed: 20 };
  root.SeamSatelliteEra = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
