import { describe, expect, it } from 'vitest';
import {
  RISK_TIER_META,
  formatCompactUsd,
  formatCompactVnd,
  formatMoney,
  formatPct,
  formatRatio,
  formatScaledVnd,
  formatSigned,
  getRiskTierMeta,
  humanizeFeature,
} from '@/lib/format';

describe('financial formatters preserve missingness', () => {
  it('never turns null, undefined, NaN, or Infinity into zero', () => {
    for (const invalid of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      expect(formatPct(invalid)).toBe('—');
      expect(formatRatio(invalid)).toBe('—');
      expect(formatSigned(invalid)).toBe('—');
      expect(formatCompactUsd(invalid)).toBe('—');
      expect(formatCompactVnd(invalid)).toBe('—');
      expect(formatMoney(invalid, 'VND')).toBe('—');
      expect(formatScaledVnd(invalid)).toBe('—');
    }
  });

  it('formats valid percentages, ratios, signed log-odds, compact USD, and compact VND accurately', () => {
    expect(formatPct(0.1842)).toBe('18.4%');
    expect(formatRatio(2.718, 2)).toBe('2.72');
    expect(formatSigned(0.3421, 3)).toBe('+0.342');
    expect(formatSigned(-0.125, 3)).toBe('-0.125');
    expect(formatCompactUsd(1_450_000_000)).toBe('$1.45B');
    expect(formatCompactUsd(-42_500_000)).toBe('-$42.5M');
    expect(formatCompactVnd(1_500_000_000)).toBe('1.50 tỷ ₫');
    expect(formatCompactVnd(-250_000_000)).toBe('-250.0 triệu ₫');
    expect(formatMoney(120, 'VND', 1_000_000)).toBe('120.0 triệu ₫');
    expect(formatMoney(50_000_000, 'USD', 1)).toBe('$50.0M');
  });

  it('exposes 4 business risk tiers without ML or agency rating codes', () => {
    expect(Object.keys(RISK_TIER_META)).toEqual(['STRONG', 'STABLE', 'WATCH', 'CRITICAL']);
    expect(getRiskTierMeta('STRONG')?.label).toBe('Vững mạnh');
    expect(getRiskTierMeta('CRITICAL')?.label).toBe('Nguy cơ khủng hoảng cao');
    const allLabels = Object.values(RISK_TIER_META)
      .map((item) => `${item.label} ${item.description}`)
      .join(' ');
    expect(allLabels).not.toMatch(/SHAP|XGBoost|Random Forest|AAA|CCC|log-odds/i);
  });

  it('maps raw backend feature names to readable Vietnamese labels', () => {
    expect(humanizeFeature('debt_ratio')).toBe('Tỷ lệ Nợ / Tổng tài sản');
    expect(humanizeFeature('altman_z_score')).toBe('Chỉ số Altman Z-Score');
    expect(humanizeFeature('custom_metric_name')).toBe('Custom Metric Name');
  });
});
