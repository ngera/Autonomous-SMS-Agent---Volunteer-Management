import { TestConversation } from "../components/test-conversation";

export function TestToolPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">SMS Test Tool</h1>
        <p className="text-sm text-muted-foreground">
          Test the AI conversation engine without sending real SMS messages.
        </p>
      </div>
      <TestConversation />
    </div>
  );
}
