import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DriversSplitPanel } from './DriversSplitPanel';
import type { DriversSplitView } from './types';

const FORBIDDEN_STRINGS = [
  'SHAP',
  'log-odds',
  'XGBoost',
  'Random Forest',
  'SMOTE',
  'AAA',
];

const SAMPLE_DRIVERS: DriversSplitView = {
  total_impact_share_pct: 100,
  strengths: [
    {
      factor_code: 'roa',
      label_vi: 'Tỷ suất sinh lời trên tài sản (ROA)',
      pillar: 'profitability',
      side: 'STRENGTH',
      observed_value: 0.112,
      formatted_value_vi: '11,2%',
      reference_range_vi: '>= 5%',
      impact_share_pct: 32.5,
      impact_strength: 'VERY_HIGH',
      impact_strength_label_vi: 'Tác động rất mạnh',
      headline_vi: 'ROA đạt 11,2%, vượt xa mức tham chiếu an toàn >= 5%.',
      detail_vi: 'Khả năng sinh lời cốt lõi vững chắc giúp gia tăng đệm vốn tự có.',
    },
    {
      factor_code: 'current_ratio',
      label_vi: 'Hệ số thanh toán ngắn hạn',
      pillar: 'liquidity',
      side: 'STRENGTH',
      observed_value: 2.15,
      formatted_value_vi: '2,15x',
      reference_range_vi: '>= 1,50x',
      impact_share_pct: 21.0,
      impact_strength: 'HIGH',
      impact_strength_label_vi: 'Tác động mạnh',
      headline_vi: 'Tài sản ngắn hạn gấp 2,15 lần nợ ngắn hạn.',
      detail_vi: 'Đảm bảo dư địa thanh khoản ổn định trong 12 tháng tới.',
    },
  ],
  bottlenecks: [
    {
      factor_code: 'debt_ratio',
      label_vi: 'Tỷ lệ nợ trên tổng tài sản',
      pillar: 'solvency',
      side: 'BOTTLENECK',
      observed_value: 0.784,
      formatted_value_vi: '78,4%',
      reference_range_vi: '<= 60%',
      impact_share_pct: 29.5,
      impact_strength: 'VERY_HIGH',
      impact_strength_label_vi: 'Tác động rất mạnh',
      headline_vi: 'Nợ phải trả chiếm 78,4% tổng tài sản (vượt ngưỡng an toàn <= 60%).',
      detail_vi: 'Đòn bẩy tài chính cao làm tăng áp lực trả lãi khi doanh thu biến động.',
    },
  ],
};

describe('DriversSplitPanel', () => {
  it('renders strengths and bottlenecks in plain Vietnamese with zero forbidden ML strings', () => {
    const { container } = render(<DriversSplitPanel drivers={SAMPLE_DRIVERS} />);

    expect(screen.getByText('Điểm Tựa & Điểm Nghẽn Tài Chính')).toBeInTheDocument();
    expect(screen.getByText(/Điểm Tựa Tài Chính \(Giảm rủi ro\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Điểm Nghẽn Tài Chính \(Đẩy rủi ro tăng\)/i)).toBeInTheDocument();

    expect(screen.getByText('Tỷ suất sinh lời trên tài sản (ROA)')).toBeInTheDocument();
    expect(screen.getByText('Hệ số thanh toán ngắn hạn')).toBeInTheDocument();
    expect(screen.getByText('Tỷ lệ nợ trên tổng tài sản')).toBeInTheDocument();
    expect(screen.getByText('32,5%')).toBeInTheDocument();
    expect(screen.getByText('29,5%')).toBeInTheDocument();

    // Critical UX gate: zero forbidden ML/agency rating strings in rendered DOM
    const domText = container.textContent ?? '';
    for (const forbidden of FORBIDDEN_STRINGS) {
      expect(domText).not.toContain(forbidden);
    }
  });

  it('handles empty strengths and bottlenecks gracefully', () => {
    const { container } = render(
      <DriversSplitPanel
        drivers={{ strengths: [], bottlenecks: [], total_impact_share_pct: 0 }}
      />,
    );

    expect(
      screen.getByText(/Chưa ghi nhận điểm tựa tài chính nổi bật/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Không ghi nhận điểm nghẽn rủi ro đáng kể/i),
    ).toBeInTheDocument();

    const domText = container.textContent ?? '';
    for (const forbidden of FORBIDDEN_STRINGS) {
      expect(domText).not.toContain(forbidden);
    }
  });
});
