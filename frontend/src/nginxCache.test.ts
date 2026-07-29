// @vitest-environment node
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const conf = readFileSync(resolve(__dirname, "../nginx.conf"), "utf8");

describe("部署缓存：nginx.conf 静态资源缓存头", () => {
  it("哈希资源 /assets/ 使用不可变长缓存", () => {
    expect(conf).toMatch(/location\s+\/assets\//);
    const assetsBlock = conf.slice(conf.indexOf("location /assets/"));
    const end = assetsBlock.indexOf("}");
    const block = assetsBlock.slice(0, end);
    expect(block).toContain("max-age=31536000");
    expect(block).toContain("immutable");
    expect(block).toContain('Cache-Control "public, max-age=31536000, immutable"');
  });

  it("SPA 入口与未哈希资源禁用缓存", () => {
    // 顶层 location / 含 no-cache（不与 /assets/ 的 immutable 冲突）
    const rootIdx = conf.indexOf("location / ");
    expect(rootIdx).toBeGreaterThan(-1);
    const rootBlock = conf.slice(rootIdx, conf.indexOf("}", rootIdx));
    expect(rootBlock).toContain("no-cache");
  });

  it("不再对全部 .js  blanket 设 no-cache（会让哈希 bundle 无法长缓存）", () => {
    expect(conf).not.toMatch(/location\s+~[^\n]*\\\.js\$/);
  });
});
