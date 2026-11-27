import { describe, expect, it } from 'vitest';
import {
  formatCompactUsd,
  formatPct,
  formatRatio,
  formatSigned,
  humanizeFeature,
} from '@/lib/format';

describe('financial formatters preserve missingness', () => {
  it('never turns null, undefined, NaN, or Infinity into zero', () => {
    for (const invalid of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      expect(formatPct(invalid)).toBe('—');
      expect(formatRatio(invalid)).toBe('—');
      expect(formatSigned(invalid)).toBe('—');
      expect(formatCompactUsd(invalid)).toBe('—');
    }
  });

  it('formats valid percentages, ratios, signed log-odds, and compact USD accurately', () => {
    expect(formatPct(0.1842)).toBe('18.4%');
    expect(formatRatio(2.718, 2)).toBe('2.72');
    expect(formatSigned(0.3421, 3)).toBe('+0.342');
    expect(formatSigned(-0.125, 3)).toBe('-0.125');
    expect(formatCompactUsd(1_450_000_000)).toBe('$1.45B');
    expect(formatCompactUsd(-42_500_000)).toBe('-$42.5M');
  });

  it('maps raw backend feature names to readable Vietnamese labels', () => {
    expect(humanizeFeature('debt_ratio')).toBe('Tỷ lệ Nợ / Tổng tài sản');
    expect(humanizeFeature('altman_z_score')).toBe('Chỉ số Altman Z-Score');
    expect(humanizeFeature('custom_metric_name')).toBe('Custom Metric Name');
  });
});
