import { useEffect, useRef, useState } from "react";

export function useChartDimensions(ref: React.RefObject<HTMLDivElement | null>) {
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const observerRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    observerRef.current = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });

    if (ref.current) observerRef.current.observe(ref.current);

    return () => observerRef.current?.disconnect();
  }, [ref]);

  return dimensions;
}
