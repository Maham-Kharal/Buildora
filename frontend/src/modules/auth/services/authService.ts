import { apiClient } from '@/core/api/client';
import { AuthResponse } from '@/core/types';

export const authService = {
  async login(email: string, password: str): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>('/auth/login', { email, password });
    return response.data;
  },

  async getMe() {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },
};
