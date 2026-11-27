import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HealthHeroCard } from './HealthHeroCard';
import type { AssessmentSummaryView } from './types';

const FORBIDDEN_STRINGS = [
  'SHAP',
  'log-odds',
  'XGBoost',
  'Random Forest',
  'SMOTE',
  'AAA',
];

const SAMPLE_SUMMARY: AssessmentSummaryView = {
  scoring_eligible: true,
  scoring_mode: 'multi_period',
  model_version: 'v2.0.0-kaggle',
  health_score: 78.4,
  risk_tier: 'STABLE',
  risk_label_vi: 'Ổn định',
  pd_12m: 0.0185,
  confidence: {
    level: 'HIGH',
    input_completeness: 0.95,
    is_ood: false,
    ood_features: [],
    ensemble_spread: 0.008,
    audit_status: 'audited_unqualified',
    reasons_vi: ['BCTC đã được kiểm toán chấp nhận toàn phần.'],
  },
  cash_flow_overlay: {
    triggered: true,
    flags: ['negative_ocf'],
    reasons_vi: ['Dòng tiền hoạt động kinh doanh âm trong khi lợi nhuận dương.'],
    original_tier: 'STRONG',
    adjusted_tier: 'STABLE',
  },
  top_3_takeaways_vi: [
    'Tỷ suất sinh lời trên tài sản duy trì tích cực ở mức 8,2%.',
    'Khả năng thanh toán ngắn hạn ở mức an toàn (1,85x).',
    'Cần theo dõi dòng tiền hoạt động do khoản phải thu tăng nhanh.',
  ],
  unavailable_reason_vi: null,
  legal_disclaimer_vi:
    'Kết quả đánh giá sức khỏe tài chính và xác suất rủi ro 12 tháng là phân tích định lượng nội bộ dựa trên mô hình học máy từ dữ liệu lịch sử, không phải dịch vụ xếp hạng tín nhiệm theo Nghị định 88/2014/NĐ-CP và không thay thế quyết định cấp tín dụng, đầu tư hay kiểm toán độc lập.',
};

describe('HealthHeroCard', () => {
  it('renders all 3-second rule elements, legal disclaimer, and zero forbidden ML strings', () => {
    const onExportPdf = vi.fn();
    const { container } = render(
      <HealthHeroCard
        summary={SAMPLE_SUMMARY}
        companyName="Công ty Cổ phần Sản xuất Minh An"
        identifierLabel="MST: 0101234567"
        sectorName="Sản xuất công nghiệp"
        fiscalYear={2025}
        accountingStandard="TT200_2014"
        currency="VND"
        onExportPdf={onExportPdf}
      />,
    );

    expect(screen.getByTestId('health-score-value')).toHaveTextContent('78,4');
    expect(screen.getByTestId('risk-tier-badge')).toHaveTextContent('Ổn định');
    expect(screen.getByTestId('pd-12m-value')).toHaveTextContent('1,85%');
    expect(screen.getByText(/Độ tin cậy: Cao/i)).toBeInTheDocument();
    expect(screen.getByText(/Cảnh báo áp lực dòng tiền/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Tỷ suất sinh lời trên tài sản duy trì tích cực/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId('legal-disclaimer')).toHaveTextContent(
      'Nghị định 88/2014/NĐ-CP',
    );

    // Toggle 4-layer confidence detail panel
    fireEvent.click(screen.getByRole('button', { name: /Độ tin cậy: Cao/i }));
    expect(screen.getByText('4 tiêu chí đánh giá độ tin cậy')).toBeInTheDocument();
    expect(screen.getByText(/Đã kiểm toán/i)).toBeInTheDocument();

    // Trigger PDF export action
    fireEvent.click(screen.getByRole('button', { name: /Xuất Báo cáo PDF/i }));
    expect(onExportPdf).toHaveBeenCalledTimes(1);

    // Critical UX gate: zero forbidden ML/agency rating strings in rendered DOM
    const domText = container.textContent ?? '';
    for (const forbidden of FORBIDDEN_STRINGS) {
      expect(domText).not.toContain(forbidden);
    }
  });

  it('renders excluded state clearly when scoring_eligible is false', () => {
    const excludedSummary: AssessmentSummaryView = {
      ...SAMPLE_SUMMARY,
      scoring_eligible: false,
      scoring_mode: 'excluded',
      health_score: null,
      risk_tier: null,
      risk_label_vi: 'Không áp dụng',
      pd_12m: null,
      confidence: null,
      cash_flow_overlay: null,
      top_3_takeaways_vi: [],
      unavailable_reason_vi:
        'Mô hình doanh nghiệp phi tài chính không áp dụng cho Ngân hàng và Tổ chức tài chính.',
    };

    const { container } = render(<HealthHeroCard summary={excludedSummary} />);

    expect(screen.getByTestId('health-score-value')).toHaveTextContent('—');
    expect(screen.getByTestId('pd-12m-value')).toHaveTextContent('—');
    expect(
      screen.getByText(/không áp dụng cho Ngân hàng và Tổ chức tài chính/i),
    ).toBeInTheDocument();

    const domText = container.textContent ?? '';
    for (const forbidden of FORBIDDEN_STRINGS) {
      expect(domText).not.toContain(forbidden);
    }
  });
});
