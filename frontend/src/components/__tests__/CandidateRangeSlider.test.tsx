import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import CandidateRangeSlider, {
  clampMin,
  clampMax,
  clampRangeToMaxCandidates,
} from "@/components/CandidateRangeSlider";

afterEach(() => {
  cleanup();
});

const bounds = { min: 0, max: 1000 };
const value = { min: 200, max: 800 };
const candidateSpends = [50, 150, 250, 500, 750, 900];

function renderSlider(overrides: {
  bounds?: typeof bounds;
  value?: typeof value;
  candidateSpends?: number[];
  onCommit?: (next: typeof value) => void;
} = {}) {
  return render(
    <CandidateRangeSlider
      bounds={overrides.bounds ?? bounds}
      value={overrides.value ?? value}
      candidateSpends={overrides.candidateSpends ?? candidateSpends}
      onCommit={overrides.onCommit ?? vi.fn()}
    />,
  );
}

function stubTrackRect(container: HTMLElement) {
  const track = container.querySelectorAll('[role="slider"]')[0]
    .parentElement as HTMLElement;
  vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
    left: 0,
    right: 400,
    width: 400,
    top: 0,
    bottom: 20,
    height: 20,
    x: 0,
    y: 0,
    toJSON: () => {},
  });
  return track;
}

describe("CandidateRangeSlider", () => {
  it("renders static bounds labels using abbreviated formatting", () => {
    const { getByText } = renderSlider();
    expect(getByText("$0")).toBeTruthy();
    expect(getByText("$1K")).toBeTruthy();
  });

  it("renders editable inputs using full comma formatting", () => {
    const { getByLabelText } = renderSlider();
    expect(
      (getByLabelText("Minimum total spending amount") as HTMLInputElement)
        .value,
    ).toBe("$200");
    expect(
      (getByLabelText("Maximum total spending amount") as HTMLInputElement)
        .value,
    ).toBe("$800");
  });

  it("shows the count of candidateSpends within the initial range", () => {
    const { getByText } = renderSlider();
    // within [200, 800]: 250, 500, 750
    expect(getByText("Candidates in range: 3")).toBeTruthy();
  });

  it("updates live count and input during drag without committing, then commits on pointer up", () => {
    const onCommit = vi.fn();
    const { container, getByLabelText, getByText } = renderSlider({
      onCommit,
    });
    stubTrackRect(container);
    const minHandle = getByLabelText("Minimum total spending");

    fireEvent.pointerDown(minHandle, { pointerId: 1 });
    fireEvent.pointerMove(minHandle, { pointerId: 1, clientX: 120 }); // 120/400 * 1000 = 300

    expect(onCommit).not.toHaveBeenCalled();
    expect(getByText("Candidates in range: 2")).toBeTruthy();
    expect(
      (getByLabelText("Minimum total spending amount") as HTMLInputElement)
        .value,
    ).toBe("$300");

    fireEvent.pointerUp(minHandle, { pointerId: 1 });
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith({ min: 300, max: 800 });
  });

  it("commits a typed value on blur, not per keystroke", () => {
    const onCommit = vi.fn();
    const { getByLabelText } = renderSlider({ onCommit });
    const minInput = getByLabelText("Minimum total spending amount");
    fireEvent.change(minInput, { target: { value: "300" } });
    expect(onCommit).not.toHaveBeenCalled();

    fireEvent.blur(minInput);
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith({ min: 300, max: 800 });
  });

  it("does not let intermediate keystrokes apply the candidate cap to the other handle", () => {
    const manySpends = Array.from({ length: 300 }, (_, i) => i + 1); // 1..300
    const onCommit = vi.fn();
    const { getByLabelText } = renderSlider({
      bounds: { min: 0, max: 300 },
      value: { min: 250, max: 300 },
      candidateSpends: manySpends,
      onCommit,
    });
    const minInput = getByLabelText("Minimum total spending amount");
    const maxInput = getByLabelText(
      "Maximum total spending amount",
    ) as HTMLInputElement;

    for (const text of ["1", "10", "100"]) {
      fireEvent.change(minInput, { target: { value: text } });
    }
    expect(onCommit).not.toHaveBeenCalled();
    expect(maxInput.value).toBe("$300");

    fireEvent.blur(minInput);
    // [100, 300] holds 201 candidates, so max is pulled in by exactly one.
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith({ min: 100, max: 299 });
    expect(maxInput.value).toBe("$299");
  });

  it("does not commit an invalid typed value until blur, then snaps to the nearest boundary", () => {
    const onCommit = vi.fn();
    const { getByLabelText } = renderSlider({ onCommit });
    const minInput = getByLabelText(
      "Minimum total spending amount",
    ) as HTMLInputElement;

    fireEvent.change(minInput, { target: { value: "999" } }); // invalid: must be < max (800)
    expect(onCommit).not.toHaveBeenCalled();

    fireEvent.blur(minInput);
    expect(onCommit).toHaveBeenCalledWith({ min: 799, max: 800 });
    expect(minInput.value).toBe("$799");
  });

  it("Enter key commits the same way as blur", () => {
    const onCommit = vi.fn();
    const { getByLabelText } = renderSlider({ onCommit });
    const maxInput = getByLabelText(
      "Maximum total spending amount",
    ) as HTMLInputElement;

    maxInput.focus();
    fireEvent.change(maxInput, { target: { value: "1500" } }); // invalid: exceeds bounds.max
    fireEvent.keyDown(maxInput, { key: "Enter" });
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith({ min: 200, max: 1000 });
  });

  it("steps the handle and commits immediately on arrow key press", () => {
    const onCommit = vi.fn();
    const { getByLabelText } = renderSlider({ onCommit });
    const minHandle = getByLabelText("Minimum total spending");
    fireEvent.keyDown(minHandle, { key: "ArrowRight" });
    // step = span / 100 = (1000 - 0) / 100 = 10
    expect(onCommit).toHaveBeenCalledWith({ min: 210, max: 800 });
  });

  it("dragging min past the 200-candidate cap pulls max down with it, live", () => {
    const manySpends = Array.from({ length: 300 }, (_, i) => i + 1); // 1..300
    const wideBounds = { min: 0, max: 300 };
    const onCommit = vi.fn();
    const { container, getByLabelText, getByText } = renderSlider({
      bounds: wideBounds,
      value: { min: 250, max: 300 },
      candidateSpends: manySpends,
      onCommit,
    });
    stubTrackRect(container);
    const minHandle = getByLabelText("Minimum total spending");

    fireEvent.pointerDown(minHandle, { pointerId: 1 });
    // clientX at the track's left edge -> raw value = bounds.min = 0
    fireEvent.pointerMove(minHandle, { pointerId: 1, clientX: 0 });

    // Uncapped this would be 300 candidates (all of 1..300); max must have
    // been pulled down to 200 to keep exactly 200 in range.
    expect(getByText("Candidates in range: 200")).toBeTruthy();
    expect(
      (getByLabelText("Minimum total spending amount") as HTMLInputElement)
        .value,
    ).toBe("$0");
    expect(
      (getByLabelText("Maximum total spending amount") as HTMLInputElement)
        .value,
    ).toBe("$200");

    fireEvent.pointerUp(minHandle, { pointerId: 1 });
    expect(onCommit).toHaveBeenCalledWith({ min: 0, max: 200 });
  });
});

describe("slider validation helpers", () => {
  it("clampMin/clampMax snap to the nearest violated boundary", () => {
    expect(clampMin(-5, 100, 0)).toBe(0);
    expect(clampMin(150, 100, 0)).toBe(99);
    expect(clampMax(500, 100, 200)).toBe(200);
    expect(clampMax(50, 100, 200)).toBe(101);
  });
});

describe("clampRangeToMaxCandidates", () => {
  // 300 distinct values, descending: [300, 299, ..., 1]
  const sortedDesc = Array.from({ length: 300 }, (_, i) => 300 - i);

  it("returns the range unchanged when the count is already within the cap", () => {
    const range = { min: 250, max: 300 }; // 51 candidates
    expect(clampRangeToMaxCandidates(range, "min", sortedDesc, 200)).toEqual(
      range,
    );
  });

  it("pulls max down when driven by min and the count exceeds the cap", () => {
    const range = { min: 1, max: 300 }; // all 300
    const result = clampRangeToMaxCandidates(range, "min", sortedDesc, 200);
    expect(result).toEqual({ min: 1, max: 200 });
    const count = sortedDesc.filter(
      (v) => v >= result.min && v <= result.max,
    ).length;
    expect(count).toBe(200);
  });

  it("pulls min up when driven by max and the count exceeds the cap", () => {
    const range = { min: 1, max: 300 }; // all 300
    const result = clampRangeToMaxCandidates(range, "max", sortedDesc, 200);
    expect(result).toEqual({ min: 101, max: 300 });
    const count = sortedDesc.filter(
      (v) => v >= result.min && v <= result.max,
    ).length;
    expect(count).toBe(200);
  });

  it("respects a custom maxCandidates value", () => {
    const range = { min: 1, max: 300 };
    const result = clampRangeToMaxCandidates(range, "min", sortedDesc, 50);
    expect(result).toEqual({ min: 1, max: 50 });
  });

  it("never inverts the range when values are tied at the boundary", () => {
    const ties = Array.from({ length: 300 }, () => 100);
    const range = { min: 100, max: 100 };
    const result = clampRangeToMaxCandidates(range, "min", ties, 50);
    expect(result.min).toBeLessThan(result.max);
  });
});
