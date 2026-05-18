import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  approveCampaign,
  cancelCampaign,
  cancelWave,
  createCampaign,
  deleteCampaign,
  editCampaignPlan,
  getCampaign,
  getWaveRecipients,
  listCampaigns,
  pauseCampaign,
  regenerateCampaignPlan,
  resumeCampaign,
  type ListCampaignsParams,
} from "../api";
import type {
  CampaignCreate,
  CampaignPlanPatch,
} from "@/types/api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useCampaigns(params: ListCampaignsParams = {}) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["recruitment-campaigns", tenantId, params],
    queryFn: () => listCampaigns(params),
    enabled: tenantId !== "none",
    refetchInterval: 30_000,
  });
}

export function useCampaign(id: string | undefined) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["recruitment-campaign", tenantId, id],
    queryFn: () => getCampaign(id!),
    enabled: !!id && tenantId !== "none",
    refetchInterval: 30_000,
  });
}

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CampaignCreate) => createCampaign(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
    },
  });
}

export function useRegeneratePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => regenerateCampaignPlan(id),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
      void qc.invalidateQueries({
        queryKey: ["recruitment-campaign", undefined, data.id],
      });
    },
  });
}

export function useEditPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CampaignPlanPatch }) =>
      editCampaignPlan(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
      void qc.invalidateQueries({ queryKey: ["recruitment-campaign"] });
    },
  });
}

export function useApproveCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => approveCampaign(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
      void qc.invalidateQueries({ queryKey: ["recruitment-campaign"] });
    },
  });
}

export function usePauseCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pauseCampaign(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
      void qc.invalidateQueries({ queryKey: ["recruitment-campaign"] });
    },
  });
}

export function useResumeCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => resumeCampaign(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
      void qc.invalidateQueries({ queryKey: ["recruitment-campaign"] });
    },
  });
}

export function useCancelCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelCampaign(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
      void qc.invalidateQueries({ queryKey: ["recruitment-campaign"] });
    },
  });
}

export function useDeleteCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteCampaign(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaigns"] });
      void qc.invalidateQueries({ queryKey: ["recruitment-campaign"] });
    },
  });
}

export function useWaveRecipients(id: string | null) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["recruitment-wave-recipients", tenantId, id],
    queryFn: () => getWaveRecipients(id!),
    enabled: !!id && tenantId !== "none",
  });
}

export function useCancelWave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelWave(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recruitment-campaign"] });
    },
  });
}
