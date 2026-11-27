import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DynamicAltmanGauge } from './DynamicAltmanGauge';
import type { AltmanView } from './types';

describe('DynamicAltmanGauge', () => {
  it('renders Altman Z with dynamic 1.81 / 2.99 cutoffs for listed manufacturing firms', () => {
    const altmanZ: AltmanView = {
      applicable: true,
      variant: 'Z',
      score: 3.45,
      zone: 'SAFE',
      zone_label_vi: 'Vùng an toàn',
      cutoff_low: 1.81,
      cutoff_high: 2.99,
      components: { X1: 0.25, X2: 0.35, X3: 0.14, X4: 2.4, X5: 1.1 },
      fallback_note_vi: null,
      unavailable_reason_vi: null,
    };

    render(<DynamicAltmanGauge altman={altmanZ} />);

    expect(screen.getByText('Altman Z-Score')).toBeInTheDocument();
    expect(screen.getByTestId('altman-score-value')).toHaveTextContent('3,45');
    expect(screen.getByTestId('altman-zone-badge')).toHaveTextContent('Vùng an toàn');
    expect(screen.getByTestId('altman-cutoff-low')).toHaveTextContent('1.81');
    expect(screen.getByTestId('altman-cutoff-high')).toHaveTextContent('2.99');
  });

  it("renders Altman Z' with dynamic 1.23 / 2.90 cutoffs and fallback note", () => {
    const altmanZPrime: AltmanView = {
      applicable: true,
      variant: "Z'",
      score: 2.05,
      zone: 'GREY',
      zone_label_vi: 'Vùng xám (cần theo dõi)',
      cutoff_low: 1.23,
      cutoff_high: 2.9,
      components: { X1: 0.12, X2: 0.18, X3: 0.08, X4: 0.9, X5: 1.05 },
      fallback_note_vi:
        "Thiếu vốn hóa thị trường; tự động chuyển sang biến thể Z' với ngưỡng 1,23 / 2,90.",
      unavailable_reason_vi: null,
    };

    render(<DynamicAltmanGauge altman={altmanZPrime} />);

    expect(screen.getByText("Altman Z'-Score")).toBeInTheDocument();
    expect(screen.getByTestId('altman-cutoff-low')).toHaveTextContent('1.23');
    expect(screen.getByTestId('altman-cutoff-high')).toHaveTextContent('2.90');
    expect(screen.getByText(/Thiếu vốn hóa thị trường/i)).toBeInTheDocument();
  });

  it("renders Altman Z'' with dynamic 1.10 / 2.60 cutoffs for non-manufacturing firms", () => {
    const altmanZDoublePrime: AltmanView = {
      applicable: true,
      variant: "Z''",
      score: 0.85,
      zone: 'DISTRESS',
      zone_label_vi: 'Vùng nguy hiểm',
      cutoff_low: 1.1,
      cutoff_high: 2.6,
      components: { X1: -0.05, X2: 0.02, X3: 0.01, X4: 0.4 },
      fallback_note_vi: null,
      unavailable_reason_vi: null,
    };

    render(<DynamicAltmanGauge altman={altmanZDoublePrime} />);

    expect(screen.getByText("Altman Z''-Score")).toBeInTheDocument();
    expect(screen.getByTestId('altman-zone-badge')).toHaveTextContent('Vùng nguy hiểm');
    expect(screen.getByTestId('altman-cutoff-low')).toHaveTextContent('1.10');
    expect(screen.getByTestId('altman-cutoff-high')).toHaveTextContent('2.60');
  });

  it('renders financial institution exclusion card when applicable is false', () => {
    const altmanExcluded: AltmanView = {
      applicable: false,
      variant: null,
      score: null,
      zone: null,
      zone_label_vi: null,
      cutoff_low: null,
      cutoff_high: null,
      components: {},
      fallback_note_vi: null,
      unavailable_reason_vi:
        'Chỉ số Altman Z-Score không áp dụng cho Ngân hàng, Bảo hiểm và Tổ chức tài chính.',
    };

    render(<DynamicAltmanGauge altman={altmanExcluded} />);

    expect(screen.getByTestId('altman-excluded-card')).toBeInTheDocument();
    expect(
      screen.getByText(/Ngân hàng, Bảo hiểm và Tổ chức tài chính/i),
    ).toBeInTheDocument();
    expect(screen.queryByTestId('altman-gauge-card')).not.toBeInTheDocument();
  });
});
