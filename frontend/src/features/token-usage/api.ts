import api from "@/lib/api";

export interface TokenUsageSummary {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_requests: number;
  estimated_cost_usd: number;
}

export interface TokenUsageBySource {
  source: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface TokenUsageByModel {
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface TokenUsageByDay {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface TokenUsageByVolunteer {
  contact_id: string | null;
  contact_phone: string | null;
  contact_name: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
  estimated_cost_usd: number;
}

export interface TokenUsageByTool {
  tool_name: string;
  call_count: number;
  request_count: number;
}

export interface TokenUsageDetail {
  id: string;
  source: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  contact_phone: string | null;
  contact_name: string | null;
  tool_names: string[];
  created_at: string;
}

export interface TokenUsageDashboard {
  summary: TokenUsageSummary;
  by_source: TokenUsageBySource[];
  by_model: TokenUsageByModel[];
  daily: TokenUsageByDay[];
  by_volunteer: TokenUsageByVolunteer[];
  by_tool: TokenUsageByTool[];
  recent: TokenUsageDetail[];
}

export async function getTokenUsageDashboard(
  days = 30
): Promise<TokenUsageDashboard> {
  const { data } = await api.get<TokenUsageDashboard>("/token-usage/dashboard", {
    params: { days },
  });
  return data;
}
