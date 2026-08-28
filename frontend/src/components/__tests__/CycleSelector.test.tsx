import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import CycleSelector from "@/components/CycleSelector";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/",
}));

afterEach(() => {
  cleanup();
});

describe("CycleSelector", () => {
  beforeEach(() => {
    push.mockClear();
  });

  it("renders one option per cycle, in the given order", () => {
    const { container } = render(
      <CycleSelector cycles={[2026, 2024]} selectedCycle={2026} />,
    );
    const options = container.querySelectorAll("option");
    expect(Array.from(options).map((o) => o.textContent)).toEqual([
      "2026",
      "2024",
    ]);
  });

  it("reflects the selected cycle in the select's value", () => {
    const { container } = render(
      <CycleSelector cycles={[2026, 2024]} selectedCycle={2024} />,
    );
    const select = container.querySelector("select") as HTMLSelectElement;
    expect(select.value).toBe("2024");
  });

  it("navigates to the new cycle's URL when the selection changes", () => {
    const { container } = render(
      <CycleSelector cycles={[2026, 2024]} selectedCycle={2026} />,
    );
    const select = container.querySelector("select") as HTMLSelectElement;

    fireEvent.change(select, { target: { value: "2024" } });

    expect(push).toHaveBeenCalledWith("/?cycle=2024");
  });
});
