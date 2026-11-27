import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { StatementEditorForm } from '@/components/statements/StatementEditorForm';

describe('StatementEditorForm and BalanceCheckAssistant', () => {
  it('auto-sums parent lines, detects balance sheet imbalance with exact line highlight, and saves draft', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<StatementEditorForm onSubmit={onSubmit} defaultFiscalYear={2025} />);

    const totalAssetsInput = screen.getByLabelText(/Tổng cộng tài sản/i) as HTMLInputElement;
    const totalLiabInput = screen.getByLabelText(/^Nợ phải trả$/i) as HTMLInputElement;
    const equityInput = screen.getByLabelText(/Vốn chủ sở hữu/i) as HTMLInputElement;

    // Enter Liabilities = 600 and Equity = 400 -> Total Assets auto-sums to 1000
    fireEvent.change(totalLiabInput, { target: { value: '600' } });
    fireEvent.change(equityInput, { target: { value: '400' } });
    expect(totalAssetsInput.value).toBe('1000');
    expect(screen.getByText(/Đạt cân đối cấu trúc/i)).toBeInTheDocument();

    // Break balance: Total Assets = 1200 != 600 + 400
    fireEvent.change(totalAssetsInput, { target: { value: '1200' } });
    expect(screen.getByText(/Bảng cân đối bị lệch/i)).toBeInTheDocument();
    expect(totalAssetsInput).toHaveAttribute('aria-invalid', 'true');

    // Finalize button must be disabled while imbalanced, but Save Draft stays enabled
    const finalizeBtn = screen.getByRole('button', { name: /Chốt báo cáo/i });
    const draftBtn = screen.getByRole('button', { name: /Lưu nháp/i });
    expect(finalizeBtn).toBeDisabled();
    expect(draftBtn).not.toBeDisabled();

    fireEvent.click(draftBtn);
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          fiscal_year: 2025,
          status: 'draft',
          unit_scale: 1_000_000,
          total_assets: 1200,
          total_liabilities: 600,
          stockholders_equity: 400,
        }),
      ),
    );
  });

  it('converts values smoothly across Đồng / Triệu đồng / Tỷ đồng and auto-sums Gross Profit', () => {
    render(<StatementEditorForm onSubmit={vi.fn()} defaultFiscalYear={2025} />);

    const totalAssetsInput = screen.getByLabelText(/Tổng cộng tài sản/i) as HTMLInputElement;
    fireEvent.change(totalAssetsInput, { target: { value: '2500' } }); // 2500 triệu đồng

    // Switch from Triệu đồng (1_000_000) to Tỷ đồng (1_000_000_000) -> 2.5
    const unitSelect = screen.getByLabelText('Đơn vị nhập liệu');
    fireEvent.change(unitSelect, { target: { value: '1000000000' } });
    expect(totalAssetsInput.value).toBe('2.5');

    // Switch to Đồng (1) -> 2500000000
    fireEvent.change(unitSelect, { target: { value: '1' } });
    expect(totalAssetsInput.value).toBe('2500000000');

    // Switch to Income Statement tab and verify Gross Profit auto-sum
    fireEvent.click(screen.getByRole('tab', { name: /Kết quả hoạt động kinh doanh/i }));
    fireEvent.change(screen.getByLabelText(/Doanh thu thuần/i), { target: { value: '1000' } });
    fireEvent.change(screen.getByLabelText(/Giá vốn hàng bán/i), { target: { value: '650' } });
    const gpInput = screen.getByLabelText(/Lợi nhuận gộp/i) as HTMLInputElement;
    expect(gpInput.value).toBe('350');
  });
});
