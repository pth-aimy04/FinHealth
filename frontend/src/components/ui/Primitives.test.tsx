import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptyState, MetricTile, RiskBadge } from '@/components/ui/Primitives';

describe('UI Primitives (Vietnamese localization)', () => {
  it('renders semantic Vietnamese labels for every risk level without relying on color alone', () => {
    render(
      <div>
        <RiskBadge level="LOW" />
        <RiskBadge level="MEDIUM" />
        <RiskBadge level="HIGH" />
        <RiskBadge level="CRITICAL" />
        <RiskBadge level={null} />
      </div>,
    );
    expect(screen.getByText('Rủi ro thấp')).toBeInTheDocument();
    expect(screen.getByText('Trung bình')).toBeInTheDocument();
    expect(screen.getByText('Rủi ro cao')).toBeInTheDocument();
    expect(screen.getByText('Nguy kịch')).toBeInTheDocument();
    expect(screen.getByText('Chưa chấm điểm')).toBeInTheDocument();
  });

  it('renders MetricTile and EmptyState with accessible status role', () => {
    render(
      <>
        <MetricTile label="Xác suất kiệt quệ" value="12.4%" meta="FY2025 · 10-K" />
        <EmptyState title="Không có kết quả" description="Hãy điều chỉnh bộ lọc." />
      </>,
    );
    expect(screen.getByText('Xác suất kiệt quệ')).toBeInTheDocument();
    expect(screen.getByText('12.4%')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Không có kết quả');
  });
});
