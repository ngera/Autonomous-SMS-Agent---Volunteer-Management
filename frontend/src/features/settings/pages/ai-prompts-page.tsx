import { PageHeader } from "@/components/shared/page-header";
import { PromptEditor, AI_PROMPT_ENTRIES } from "../components/prompt-editor";

export function AiPromptsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Prompts"
        description="System prompts that drive the AI assistant for SMS conversations and the recruitment agent. Edits are saved per-tenant; reset any prompt to fall back to the shipped default."
      />
      <PromptEditor entries={AI_PROMPT_ENTRIES} title="AI Prompts" />
    </div>
  );
}
