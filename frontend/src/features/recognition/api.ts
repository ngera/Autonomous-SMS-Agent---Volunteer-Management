import api from "@/lib/api";
import type {
  AwardDefinitionRow,
  DefinitionCreatePayload,
  DefinitionUpdatePayload,
  ManualGrantPayload,
  RecognitionRow,
} from "@/types/api";

export async function listDefinitions(
  includeInactive: boolean = false
): Promise<AwardDefinitionRow[]> {
  const { data } = await api.get<AwardDefinitionRow[]>(
    "/recognition/definitions",
    { params: { include_inactive: includeInactive } }
  );
  return data;
}

export async function createDefinition(
  body: DefinitionCreatePayload
): Promise<AwardDefinitionRow> {
  const { data } = await api.post<AwardDefinitionRow>(
    "/recognition/definitions",
    body
  );
  return data;
}

export async function updateDefinition(
  id: string,
  body: DefinitionUpdatePayload
): Promise<AwardDefinitionRow> {
  const { data } = await api.put<AwardDefinitionRow>(
    `/recognition/definitions/${id}`,
    body
  );
  return data;
}

export async function deactivateDefinition(id: string): Promise<void> {
  await api.delete(`/recognition/definitions/${id}`);
}

export async function grantRecognition(
  body: ManualGrantPayload
): Promise<RecognitionRow> {
  const { data } = await api.post<RecognitionRow>("/recognition/grant", body);
  return data;
}

export async function listRecognitionsForContact(
  contactId: string
): Promise<RecognitionRow[]> {
  const { data } = await api.get<RecognitionRow[]>(
    `/recognition/contact/${contactId}`
  );
  return data;
}
