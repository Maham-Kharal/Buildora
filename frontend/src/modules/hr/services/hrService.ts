import { apiClient } from '@/core/api/client';
import { UserProfile, LeaveRequest, CompanyPolicy } from '@/core/types';

export const hrService = {
  async getUsers(): Promise<UserProfile[]> {
    const response = await apiClient.get<UserProfile[]>('/hr/users');
    return response.data;
  },

  async createUser(data: { email: string; full_name: string; role: string; password: str }): Promise<UserProfile> {
    const response = await apiClient.post<UserProfile>('/hr/users', data);
    return response.data;
  },

  async resetPassword(userId: number, newPassword: string) {
    const response = await apiClient.patch(`/hr/users/${userId}/reset-password`, { new_password: newPassword });
    return response.data;
  },

  async getLeaves(): Promise<LeaveRequest[]> {
    const response = await apiClient.get<LeaveRequest[]>('/hr/leaves');
    return response.data;
  },

  async updateLeaveStatus(leaveId: number, status: 'APPROVED' | 'REJECTED') {
    const response = await apiClient.patch(`/hr/leaves/${leaveId}/status`, { status });
    return response.data;
  },

  async getPolicies(): Promise<CompanyPolicy[]> {
    const response = await apiClient.get<CompanyPolicy[]>('/hr/policies');
    return response.data;
  },

  async createPolicy(data: { title: string; category: string; content: string }): Promise<CompanyPolicy> {
    const response = await apiClient.post<CompanyPolicy>('/hr/policies', data);
    return response.data;
  },

  async deletePolicy(policyId: number) {
    const response = await apiClient.delete(`/hr/policies/${policyId}`);
    return response.data;
  },
};
