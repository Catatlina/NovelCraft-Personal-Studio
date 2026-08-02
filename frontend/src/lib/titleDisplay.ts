export function cleanNovelTitle(value: unknown, fallback = "未命名小说"): string {
  const title = String(value ?? "").trim().replace(/^《+/, "").replace(/》+$/, "").trim();
  return title || fallback;
}

export function bookTitle(value: unknown, fallback = "未命名小说"): string {
  return `《${cleanNovelTitle(value, fallback)}》`;
}
