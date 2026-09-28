import { apiClient } from '@/core/api/client';
import { Receipt, AssignedProject } from '@/core/types';

export const userService = {
  async getAssignedProjects(): Promise<AssignedProject[]> {
    const response = await apiClient.get<AssignedProject[]>('/user/receipts/assigned-projects');
    return response.data;
  },

  async uploadReceipt(file: File, projectId: number): Promise<Receipt> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', String(projectId));
    const response = await apiClient.post<Receipt>('/user/receipts/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async getMyReceipts(): Promise<Receipt[]> {
    const response = await apiClient.get<Receipt[]>('/user/receipts/my-receipts');
    return response.data;
  },


  async askHRAssistant(prompt: string, sessionId?: string, role?: string): Promise<{ answer: string; auto_approved_leave: boolean; intent?: string; session_id?: string }> {
    const response = await apiClient.post<{ answer: string; auto_approved_leave: boolean; intent?: string; session_id?: string }>(
      '/user/hr-assistant/ask',
      { prompt, session_id: sessionId || 'default_session', role }
    );
    return response.data;
  },
};
