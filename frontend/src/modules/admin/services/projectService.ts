import { apiClient } from '@/core/api/client';
import { ActiveProject, ProjectCreatePayload, AssignableUser } from '@/core/types';

export const projectService = {
  async getProjects(): Promise<ActiveProject[]> {
    const response = await apiClient.get<ActiveProject[]>('/admin/projects');
    return response.data;
  },

  async getAssignableUsers(): Promise<AssignableUser[]> {
    const response = await apiClient.get<AssignableUser[]>('/admin/projects/assignable-users');
    return response.data;
  },

  async createProject(payload: ProjectCreatePayload): Promise<ActiveProject> {
    const response = await apiClient.post<ActiveProject>('/admin/projects', payload);
    return response.data;
  },

  async deleteProject(projectId: number): Promise<void> {
    await apiClient.delete(`/admin/projects/${projectId}`);
  },

  async updateProjectStatus(projectId: number, status: 'ACTIVE' | 'COMPLETED'): Promise<ActiveProject> {
    const response = await apiClient.patch<ActiveProject>(`/admin/projects/${projectId}/status`, { status });
    return response.data;
  },
};

