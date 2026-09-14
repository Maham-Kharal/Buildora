export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: 'WORKER' | 'ADMIN' | 'HR_MANAGER';
  is_active?: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  role: 'WORKER' | 'ADMIN' | 'HR_MANAGER';
  user_id: number;
  full_name: string;
}

export interface ReceiptItem {
  id?: number;
  item_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface Receipt {
  id: number;
  user_id: number;
  user_name?: string;
  user_email?: string;
  image_url: string;
  vendor_name: string;
  total_amount: number;
  purchase_date?: string;
  category?: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  flagged_anomaly: boolean;
  created_at: string;
  items: ReceiptItem[];
}

export interface CategoryBreakdown {
  category: string;
  total_amount: number;
  receipt_count: number;
}

export interface ExpenseReportSummary {
  total_spend_usd: number;
  total_receipts: number;
  flagged_anomalies_count: number;
  pending_approval_count: number;
  approved_count: number;
  rejected_count: number;
  by_category: CategoryBreakdown[];
}

export interface SimilarProject {
  name: string;
  project_type: string;
  sqft: number;
  steel_tons_used: number;
  cost_usd: number;
  location: string;
  similarity_score: number;
}

export interface SteelEstimateResponse {
  project_name: str;
  total_sqft: number;
  estimated_rebar_tons: number;
  live_market_price_per_ton: number;
  total_estimated_cost_usd: number;
  currency: string;
  market_source: string;
  similar_historical_projects: SimilarProject[];
}

export interface LeaveRequest {
  id: number;
  user_id: number;
  user_name?: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  auto_approved: boolean;
  created_at: string;
}

export interface CompanyPolicy {
  id: number;
  title: string;
  category: string;
  content: string;
  created_at: string;
}

export interface AuditLog {
  id: number;
  user_id?: number;
  user_name?: string;
  action: string;
  details: string;
  created_at: string;
}
