import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it } from "vitest";

import { apiErrorMessage } from "./api";

function axiosError(status: number, data: unknown): AxiosError {
  const err = new AxiosError("boom");
  err.response = {
    status,
    data,
    statusText: "",
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return err;
}

describe("apiErrorMessage", () => {
  it("returns the server's own explanation", () => {
    // The site settings PUT names the offending location AND what is available — collapsing that
    // into a generic toast was the bug this helper exists to fix.
    const detail = "not served by the squad: Narnia — available: Germany, Finland";
    expect(apiErrorMessage(axiosError(400, { detail }), "ذخیره نشد.")).toBe(detail);
  });

  it("pulls the first message out of a 422 validation body", () => {
    const err = axiosError(422, {
      detail: [{ loc: ["body", "slug"], msg: "slug must be lowercase" }],
    });
    expect(apiErrorMessage(err, "ذخیره نشد.")).toBe("slug must be lowercase");
  });

  it("falls back when the body carries no usable detail", () => {
    expect(apiErrorMessage(axiosError(500, {}), "ذخیره نشد.")).toBe("ذخیره نشد.");
    expect(apiErrorMessage(axiosError(400, { detail: "   " }), "ذخیره نشد.")).toBe("ذخیره نشد.");
  });

  it("distinguishes a network failure from a server rejection", () => {
    expect(apiErrorMessage(new AxiosError("Network Error"), "ذخیره نشد.")).toBe(
      "ارتباط با سرور برقرار نشد.",
    );
  });

  it("passes non-axios errors through to the fallback", () => {
    expect(apiErrorMessage(new Error("nope"), "ذخیره نشد.")).toBe("ذخیره نشد.");
  });
});
