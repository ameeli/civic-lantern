function hexToRgb01(hex: string) {
  const n = parseInt(hex.replace("#", ""), 16);
  return {
    r: ((n >> 16) & 255) / 255,
    g: ((n >> 8) & 255) / 255,
    b: (n & 255) / 255,
  };
}

export default function PaperBorder({ color = "#e2d7b8" }: { color?: string }) {
  const { r, g, b } = hexToRgb01(color);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="100%"
      height="100%"
      aria-hidden="true"
      className="absolute inset-0 pointer-events-none"
    >
      <defs>
        {/* Edge warp */}
        <filter id="warp" x="-5%" y="-5%" width="110%" height="110%">
          <feMorphology
            in="SourceGraphic"
            operator="erode"
            radius="25"
            result="eroded"
          />
          <feTurbulence
            type="turbulence"
            baseFrequency="0.032"
            numOctaves="4"
            seed="5"
            result="n"
          />
          <feDisplacementMap
            in="eroded"
            in2="n"
            scale="7"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>

        <mask id="paper-edge">
          <rect width="100%" height="100%" fill="white" filter="url(#warp)" />
        </mask>

        {/* Paper texture */}
        <filter
          id="paper"
          x="0%"
          y="0%"
          width="100%"
          height="100%"
          colorInterpolationFilters="sRGB"
        >
          {/* Aging patches */}
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.02"
            numOctaves="3"
            seed="7"
            result="aging"
          />
          {/* Map noise to newsprint color range */}
          <feColorMatrix
            type="matrix"
            values={`0.07 0 0 0 ${r.toFixed(3)}
                    0.06 0 0 0 ${g.toFixed(3)}
                    0.05 0 0 0 ${b.toFixed(3)}
                    0    0 0 0.35 0.2`}
            in="aging"
            result="agingColor"
          />

          {/* Fine newsprint grain (high freq) */}
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.80"
            numOctaves="4"
            seed="3"
            result="grain"
          />
          <feColorMatrix
            type="saturate"
            values="0"
            in="grain"
            result="grayGrain"
          />
          <feComponentTransfer in="grayGrain" result="lightGrain">
            <feFuncR type="linear" slope={0.3} intercept={0.7} />
            <feFuncG type="linear" slope={0.3} intercept={0.7} />
            <feFuncB type="linear" slope={0.3} intercept={0.7} />
            <feFuncA type="linear" slope={0} intercept={0.7} />
          </feComponentTransfer>
          <feBlend
            in="agingColor"
            in2="lightGrain"
            mode="multiply"
            result="textured"
          />

          {/* Foxing spots — threshold turbulence to top ~6% of values */}
          <feTurbulence
            type="turbulence"
            baseFrequency="0.06"
            numOctaves="2"
            seed="21"
            result="spots"
          />
          <feComponentTransfer in="spots" result="spotThresh">
            <feFuncR
              type="discrete"
              tableValues="0 0 0 0 0 0 0 0 0 0 1 1 1 1 1 1"
            />
            <feFuncG
              type="discrete"
              tableValues="0 0 0 0 0 0 0 0 0 0 1 1 1 1 1 1"
            />
            <feFuncB
              type="discrete"
              tableValues="0 0 0 0 0 0 0 0 0 0 1 1 1 1 1 1"
            />
          </feComponentTransfer>
          {/* Promote R channel to alpha to use as compositing mask */}
          <feColorMatrix
            type="matrix"
            values="0 0 0 0 0
                    0 0 0 0 0
                    0 0 0 0 0
                    1 0 0 0 0"
            in="spotThresh"
            result="spotAlpha"
          />
          <feFlood
            floodColor="#8a6f4a"
            floodOpacity="0.08"
            result="spotColor"
          />
          <feComposite
            in="spotColor"
            in2="spotAlpha"
            operator="in"
            result="foxing"
          />

          <feMerge>
            <feMergeNode in="textured" />
            <feMergeNode in="foxing" />
          </feMerge>
        </filter>
      </defs>

      {/* Paper texture with warped edges — fills the full container */}
      <g mask="url(#paper-edge)">
        <rect width="100%" height="100%" filter="url(#paper)" />
      </g>
    </svg>
  );
}
