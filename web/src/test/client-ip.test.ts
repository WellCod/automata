import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { clientIp } from "@/lib/bff/client-ip";

function req(headers: Record<string, string>): NextRequest {
  return new NextRequest("http://localhost/api/auth/login", { headers });
}

describe("clientIp", () => {
  it("prefere x-real-ip", () => {
    expect(clientIp(req({ "x-real-ip": "1.1.1.1", "x-forwarded-for": "2.2.2.2" }))).toBe("1.1.1.1");
  });

  it("usa o primeiro hop do x-forwarded-for", () => {
    expect(clientIp(req({ "x-forwarded-for": "3.3.3.3, 10.0.0.1" }))).toBe("3.3.3.3");
  });

  it("retorna null sem cabeçalhos", () => {
    expect(clientIp(req({}))).toBeNull();
  });
});
