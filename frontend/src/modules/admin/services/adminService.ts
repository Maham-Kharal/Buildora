import { apiClient } from '@/core/api/client';
import { Receipt, ExpenseReportSummary, SteelEstimateResponse, AuditLog } from '@/core/types';

export const adminService = {
  async getReceipts(): Promise<Receipt[]> {
    const response = await apiClient.get<Receipt[]>('/admin/receipts');
    return response.data;
  },

  async updateReceiptStatus(receiptId: number, status: 'APPROVED' | 'REJECTED') {
    const response = await apiClient.patch(`/admin/receipts/${receiptId}/status`, { status });
    return response.data;
  },

  async getExpenseSummary(): Promise<ExpenseReportSummary> {
    const response = await apiClient.get<ExpenseReportSummary>('/admin/expense-reports/summary');
    return response.data;
  },

  async estimateSteel(data: {
    project_name: string;
    project_type: string;
    total_sqft: number;
    rebar_grade: string;
    location: string;
  }): Promise<SteelEstimateResponse> {
    const response = await apiClient.post<SteelEstimateResponse>('/admin/steel-estimator/estimate', data);
    return response.data;
  },

  async getAuditLogs(): Promise<AuditLog[]> {
    const response = await apiClient.get<AuditLog[]>('/admin/audit-logs');
    return response.data;
  },

  async askAdminAIChat(prompt: string, sessionId?: string): Promise<{ message: string; answer: string; intent?: string; session_id?: string; structured_data?: any }> {
    const response = await apiClient.post<{ message?: string; answer?: string; response?: string; intent?: string; session_id?: string; structured_data?: any }>(
      '/admin/ai/chat',
      { message: prompt, session_id: sessionId || 'default_admin_session' }
    );
    const text = response.data.message || response.data.answer || response.data.response || 'No response message received.';
    return {
      message: text,
      answer: text,
      intent: response.data.intent,
      session_id: response.data.session_id,
      structured_data: response.data.structured_data
    };
  },
};
