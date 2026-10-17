export function discussPrompt(current: string, parent: string | null): string {
  const text = current.trim();
  const upper = parent?.trim() ?? "";
  if (upper) {
    return `Discuss what these sources say about ${text}, in the larger context of ${upper}.`;
  }
  return `Discuss what these sources say about ${text}.`;
}
