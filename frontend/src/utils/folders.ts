/** Helpers for nested mail folder display in selects. */

export function folderDepth(pathOrName: string): number {
  const parts = pathOrName.split(/[/\\]/).map((p) => p.trim()).filter(Boolean);
  return Math.max(0, parts.length - 1);
}

export function folderLeafName(pathOrName: string, fallback = ""): string {
  const parts = pathOrName.split(/[/\\]/).map((p) => p.trim()).filter(Boolean);
  return parts[parts.length - 1] || fallback || pathOrName;
}
