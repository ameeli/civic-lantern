import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import CandidateRangeSlider, {
  isValidMin,
  isValidMax,
  clampMin,
  clampMax,
} from "@/components/CandidateRangeSlider";

afterEach(() => {
  cleanup();
});

const bounds = { min: 0, max: 1000 };
const value = { min: 200, max: 800 };
const candidateSpends = [50, 150, 250, 500, 750, 900];

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
    const { getByText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={vi.fn()}
      />,
    );
    expect(getByText("$0")).toBeTruthy();
    expect(getByText("$1K")).toBeTruthy();
  });

  it("renders editable inputs using full comma formatting", () => {
    const { getByLabelText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={vi.fn()}
      />,
    );
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
    const { getByText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={vi.fn()}
      />,
    );
    // within [200, 800]: 250, 500, 750
    expect(getByText("Candidates in range: 3")).toBeTruthy();
  });

  it("updates live count and input during drag without committing, then commits on pointer up", () => {
    const onCommit = vi.fn();
    const { container, getByLabelText, getByText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={onCommit}
      />,
    );
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

  it("commits immediately per keystroke when the typed value is valid", () => {
    const onCommit = vi.fn();
    const { getByLabelText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={onCommit}
      />,
    );
    const minInput = getByLabelText("Minimum total spending amount");
    fireEvent.change(minInput, { target: { value: "300" } });
    expect(onCommit).toHaveBeenCalledWith({ min: 300, max: 800 });
  });

  it("does not commit an invalid typed value until blur, then snaps to the nearest boundary", () => {
    const onCommit = vi.fn();
    const { getByLabelText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={onCommit}
      />,
    );
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
    const { getByLabelText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={onCommit}
      />,
    );
    const maxInput = getByLabelText(
      "Maximum total spending amount",
    ) as HTMLInputElement;

    fireEvent.change(maxInput, { target: { value: "1500" } }); // invalid: exceeds bounds.max
    fireEvent.keyDown(maxInput, { key: "Enter" });
    expect(onCommit).toHaveBeenCalledWith({ min: 200, max: 1000 });
  });

  it("steps the handle and commits immediately on arrow key press", () => {
    const onCommit = vi.fn();
    const { getByLabelText } = render(
      <CandidateRangeSlider
        bounds={bounds}
        value={value}
        candidateSpends={candidateSpends}
        onCommit={onCommit}
      />,
    );
    const minHandle = getByLabelText("Minimum total spending");
    fireEvent.keyDown(minHandle, { key: "ArrowRight" });
    // step = span / 100 = (1000 - 0) / 100 = 10
    expect(onCommit).toHaveBeenCalledWith({ min: 210, max: 800 });
  });
});

describe("slider validation helpers", () => {
  it("isValidMin/isValidMax enforce strict ordering within bounds", () => {
    expect(isValidMin(50, 100, 0)).toBe(true);
    expect(isValidMin(-1, 100, 0)).toBe(false);
    expect(isValidMin(100, 100, 0)).toBe(false);
    expect(isValidMax(150, 100, 200)).toBe(true);
    expect(isValidMax(100, 100, 200)).toBe(false);
    expect(isValidMax(300, 100, 200)).toBe(false);
  });

  it("clampMin/clampMax snap to the nearest violated boundary", () => {
    expect(clampMin(-5, 100, 0)).toBe(0);
    expect(clampMin(150, 100, 0)).toBe(99);
    expect(clampMax(500, 100, 200)).toBe(200);
    expect(clampMax(50, 100, 200)).toBe(101);
  });
});
