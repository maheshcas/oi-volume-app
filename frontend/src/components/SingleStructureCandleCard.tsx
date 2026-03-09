import { useMemo } from "react";
import ReactECharts from "echarts-for-react";

type Props = {
  open: number;
  high: number;
  low: number;
  close: number;
  spot: number;
  title?: string;
  subtitle?: string;
  bias?: string;
  regime?: string;
  support?: number | null;
  resistance?: number | null;
  supportStart?: number | null;
  supportEnd?: number | null;
  resistanceStart?: number | null;
  resistanceEnd?: number | null;
  target1?: number | null;
  target2?: number | null;
  width?: number;
  height?: number;
};

function formatValue(value: number | null | undefined, digits = 1) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtIN(value: number | null | undefined, digits = 0) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function inferTrapRisk(subtitle?: string) {
  const text = String(subtitle ?? "").toLowerCase();
  if (text.includes("high")) return { label: "High", pct: 75 };
  if (text.includes("moderate")) return { label: "Moderate", pct: 50 };
  if (text.includes("low")) return { label: "Low", pct: 25 };
  return { label: "-", pct: 0 };
}

export default function SingleStructureCandleCard({
  open,
  high,
  low,
  close,
  spot,
  title,
  subtitle,
  bias,
  regime,
  support,
  resistance,
  supportStart,
  supportEnd,
  resistanceStart,
  resistanceEnd,
  target1,
  target2,
  width = 1000,
  height = 320,
}: Props) {
  const supportCenter = typeof support === "number" ? support : null;
  const resistanceCenter = typeof resistance === "number" ? resistance : null;
  const supportZoneTop =
    typeof supportStart === "number" && typeof supportEnd === "number"
      ? Math.max(supportStart, supportEnd)
      : supportCenter;
  const supportZoneBot =
    typeof supportStart === "number" && typeof supportEnd === "number"
      ? Math.min(supportStart, supportEnd)
      : supportCenter;
  const resistanceZoneTop =
    typeof resistanceStart === "number" && typeof resistanceEnd === "number"
      ? Math.max(resistanceStart, resistanceEnd)
      : resistanceCenter;
  const resistanceZoneBot =
    typeof resistanceStart === "number" && typeof resistanceEnd === "number"
      ? Math.min(resistanceStart, resistanceEnd)
      : resistanceCenter;

  const trapRisk = inferTrapRisk(subtitle);
  const trapType = title ?? subtitle?.replace(/^Trap Zone:\s*/i, "") ?? "-";
  const pressureLabel = regime ?? "-";
  const mssScore = bias ?? "-";

  const option = useMemo(() => {
    const srGap =
      typeof supportCenter === "number" && typeof resistanceCenter === "number"
        ? resistanceCenter - supportCenter
        : 0;
    const PAD = Math.max(80, srGap * 0.12);
    const lowerBase =
      typeof supportZoneBot === "number"
        ? supportZoneBot
        : Math.min(low, open, close, spot, target1 ?? Number.POSITIVE_INFINITY, target2 ?? Number.POSITIVE_INFINITY);
    const upperBase =
      typeof resistanceZoneTop === "number"
        ? resistanceZoneTop
        : Math.max(high, open, close, spot, target1 ?? Number.NEGATIVE_INFINITY, target2 ?? Number.NEGATIVE_INFINITY);
    const yMin = lowerBase - PAD;
    const yMax = upperBase + PAD;
    const isBearish = spot < open;
    const chartHeight = Math.max(320, height) - 44;
    const chartInnerWidth = width - 70 - 116;
    const priceToY = (price: number) => 22 + ((yMax - price) / (yMax - yMin)) * chartHeight;

    const labels = [
      ...(typeof resistanceCenter === "number"
        ? [{ key: "resistance", y: priceToY(resistanceCenter), text: `R  ${fmtIN(resistanceCenter)}`, fill: "#f87171", bg: "rgba(239,68,68,0.12)", border: "rgba(239,68,68,0.32)" }]
        : []),
      { key: "spot", y: priceToY(spot), text: `SPOT  ${fmtIN(spot, 1)}`, fill: "#fbbf24", bg: "rgba(245,158,11,0.14)", border: "rgba(245,158,11,0.38)" },
      ...(typeof supportCenter === "number"
        ? [{ key: "support", y: priceToY(supportCenter), text: `S  ${fmtIN(supportCenter)}`, fill: "#34d399", bg: "rgba(16,185,129,0.12)", border: "rgba(16,185,129,0.32)" }]
        : []),
    ].sort((a, b) => a.y - b.y);

    const MIN_GAP = 18;
    for (let i = 1; i < labels.length; i += 1) {
      if (labels[i].y - labels[i - 1].y < MIN_GAP) {
        labels[i].y = labels[i - 1].y + MIN_GAP;
      }
    }

    const graphics = [
      ...(typeof supportCenter === "number" && typeof resistanceCenter === "number"
        ? [
            {
              type: "rect",
              left: 70,
              top: priceToY(resistanceCenter),
              shape: {
                x: 0,
                y: 0,
                width: 2,
                height: Math.max(priceToY(supportCenter) - priceToY(resistanceCenter), 2),
              },
              style: {
                fill: "rgba(245,158,11,0.42)",
              },
              silent: true,
            },
          ]
        : []),
      ...labels.flatMap((label) => [
        {
          type: "rect",
          left: 70 + chartInnerWidth + 3,
          top: label.y - 10,
          shape: {
            x: 0,
            y: 0,
            width: 104,
            height: label.key === "spot" ? 18 : 16,
            r: 5,
          },
          style: {
            fill: label.bg,
            stroke: label.border,
            lineWidth: 1,
          },
          silent: true,
        },
        {
          type: "text",
          left: 70 + chartInnerWidth + 9,
          top: label.y - 2,
          style: {
            text: label.text,
            fill: label.fill,
            font: `${label.key === "spot" ? 800 : 700} ${label.key === "spot" ? 12 : 10}px JetBrains Mono, monospace`,
          },
          silent: true,
        },
      ]),
    ];

    return {
      backgroundColor: "transparent",
      animation: true,
      animationDuration: 700,
      animationEasing: "cubicOut",
      grid: { left: 70, right: 116, top: 22, bottom: 22, containLabel: false },
      xAxis: {
        type: "category",
        data: ["Session"],
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: yMin,
        max: yMax,
        splitNumber: 8,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          show: true,
          lineStyle: {
            color: "rgba(148,163,184,0.07)",
          },
        },
        axisLabel: {
          color: "#334155",
          fontFamily: "JetBrains Mono, monospace",
          formatter: (value: number) => value.toLocaleString("en-IN"),
        },
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(4,10,22,0.96)",
        borderColor: "rgba(255,255,255,0.10)",
        borderRadius: 12,
        padding: [10, 14],
        textStyle: {
          color: "#e2e8f0",
          fontFamily: "JetBrains Mono, monospace",
        },
        axisPointer: {
          type: "cross",
          label: {
            backgroundColor: "rgba(4,10,22,0.96)",
            color: "#e2e8f0",
            borderColor: "rgba(255,255,255,0.10)",
            borderWidth: 1,
            fontFamily: "JetBrains Mono, monospace",
            formatter: ({ value }: { value: number }) =>
              typeof value === "number" ? value.toLocaleString("en-IN") : "",
          },
          lineStyle: {
            color: "rgba(255,255,255,0.10)",
            type: "dashed",
          },
          crossStyle: {
            color: "rgba(255,255,255,0.10)",
            type: "dashed",
          },
        },
        formatter: () =>
          [
            '<div style="display:grid;gap:6px;min-width:190px">',
            `<div><span style="color:#93c5fd">Open</span> <strong>${formatValue(open, 1)}</strong></div>`,
            `<div><span style="color:#34d399">High</span> <strong>${formatValue(high, 1)}</strong></div>`,
            `<div><span style="color:#f87171">Low</span> <strong>${formatValue(low, 1)}</strong></div>`,
            `<div><span style="color:#fbbf24">Spot</span> <strong>${formatValue(spot, 1)}</strong></div>`,
            '<div style="height:1px;background:rgba(255,255,255,0.08);margin:4px 0"></div>',
            `<div><span style="color:#34d399">Support</span> <strong>${formatValue(supportCenter, 0)}</strong></div>`,
            `<div><span style="color:#f87171">Resistance</span> <strong>${formatValue(resistanceCenter, 0)}</strong></div>`,
            "</div>",
          ].join(""),
      },
      graphic: graphics,
      series: [
        {
          type: "line",
          data: [],
          silent: true,
          markArea:
            typeof resistanceZoneBot === "number" && typeof resistanceZoneTop === "number"
              ? {
                  itemStyle: {
                    color: {
                      type: "linear",
                      x: 0,
                      y: 0,
                      x2: 0,
                      y2: 1,
                      colorStops: [
                        { offset: 0, color: "rgba(239,68,68,0.22)" },
                        { offset: 1, color: "rgba(239,68,68,0.05)" },
                      ],
                    },
                    borderColor: "rgba(239,68,68,0.28)",
                    borderWidth: 1,
                    borderType: "dashed",
                  },
                  label: {
                    show: true,
                    position: "insideTopRight",
                    color: "rgba(248,113,113,0.75)",
                    fontSize: 9,
                    fontWeight: "bold",
                    formatter: "RESISTANCE ZONE",
                  },
                  data: [[{ yAxis: resistanceZoneBot }, { yAxis: resistanceZoneTop }]],
                }
              : undefined,
        },
        {
          type: "line",
          data: [],
          silent: true,
          markArea:
            typeof supportZoneBot === "number" && typeof supportZoneTop === "number"
              ? {
                  itemStyle: {
                    color: {
                      type: "linear",
                      x: 0,
                      y: 1,
                      x2: 0,
                      y2: 0,
                      colorStops: [
                        { offset: 0, color: "rgba(16,185,129,0.06)" },
                        { offset: 1, color: "rgba(16,185,129,0.22)" },
                      ],
                    },
                    borderColor: "rgba(16,185,129,0.28)",
                    borderWidth: 1,
                    borderType: "dashed",
                  },
                  label: {
                    show: true,
                    position: "insideBottomRight",
                    color: "rgba(52,211,153,0.75)",
                    fontSize: 9,
                    fontWeight: "bold",
                    formatter: "SUPPORT ZONE",
                  },
                  data: [[{ yAxis: supportZoneBot }, { yAxis: supportZoneTop }]],
                }
              : undefined,
        },
        {
          type: "line",
          data: [],
          silent: true,
          markArea:
            typeof supportCenter === "number" && typeof resistanceCenter === "number"
              ? {
                  itemStyle: {
                    color: {
                      type: "linear",
                      x: 0,
                      y: 0,
                      x2: 0,
                      y2: 1,
                      colorStops: [
                        { offset: 0, color: "rgba(245,158,11,0.08)" },
                        { offset: 0.5, color: "rgba(245,158,11,0.03)" },
                        { offset: 1, color: "rgba(245,158,11,0.08)" },
                      ],
                    },
                  },
                  label: {
                    show: true,
                    position: [8, 16],
                    color: "rgba(245,158,11,0.35)",
                    fontSize: 9,
                    fontWeight: "bold",
                    formatter: "TRAP",
                  },
                  data: [[{ yAxis: supportCenter }, { yAxis: resistanceCenter }]],
                }
              : undefined,
        },
        {
          type: "candlestick",
          barWidth: "30%",
          data: [[open, spot, low, high]],
          itemStyle: {
            color: "rgba(0,0,0,0)",
            color0: "rgba(0,0,0,0)",
            borderColor: "rgba(0,0,0,0)",
            borderColor0: "rgba(0,0,0,0)",
            borderWidth: 0,
          },
          markArea: {
            silent: true,
            itemStyle: {
              color: isBearish ? "rgba(239,68,68,0.08)" : "rgba(16,185,129,0.08)",
            },
            data: [[{ yAxis: low, xAxis: "Session" }, { yAxis: high, xAxis: "Session" }]],
          },
          markLine: {
            symbol: ["none", "none"],
            animation: true,
            animationDelay: 150,
            data: [
              {
                yAxis: spot,
                lineStyle: {
                  color: "#fbbf24",
                  width: 2,
                  type: [10, 6],
                  shadowBlur: 14,
                  shadowColor: "rgba(245,158,11,0.70)",
                },
                label: {
                  show: false,
                  position: "end",
                  formatter: `SPOT  ${spot.toLocaleString("en-IN", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}`,
                  color: "#fbbf24",
                  fontWeight: "bold",
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 12,
                  backgroundColor: "rgba(245,158,11,0.14)",
                  borderColor: "rgba(245,158,11,0.38)",
                  borderWidth: 1,
                  borderRadius: 5,
                  padding: [4, 9],
                },
              },
              ...(typeof resistanceCenter === "number"
                ? [
                    {
                      yAxis: resistanceCenter,
                      lineStyle: {
                        color: "#ef4444",
                        width: 1.5,
                        type: [8, 5],
                        opacity: 0.7,
                      },
                      label: {
                        show: false,
                        position: "end",
                        formatter: `R  ${resistanceCenter.toLocaleString("en-IN")}`,
                        color: "#f87171",
                        fontFamily: "JetBrains Mono, monospace",
                        backgroundColor: "rgba(239,68,68,0.12)",
                        borderColor: "rgba(239,68,68,0.32)",
                        borderWidth: 1,
                        borderRadius: 5,
                        padding: [3, 8],
                      },
                    },
                  ]
                : []),
              ...(typeof supportCenter === "number"
                ? [
                    {
                      yAxis: supportCenter,
                      lineStyle: {
                        color: "#10b981",
                        width: 1.5,
                        type: [8, 5],
                        opacity: 0.7,
                      },
                      label: {
                        show: false,
                        position: "end",
                        formatter: `S  ${supportCenter.toLocaleString("en-IN")}`,
                        color: "#34d399",
                        fontFamily: "JetBrains Mono, monospace",
                        backgroundColor: "rgba(16,185,129,0.12)",
                        borderColor: "rgba(16,185,129,0.32)",
                        borderWidth: 1,
                        borderRadius: 5,
                        padding: [3, 8],
                      },
                    },
                  ]
                : []),
            ],
          },
          emphasis: {
            disabled: true,
          },
        },
        {
          type: "custom",
          silent: true,
          data: [[0, open, spot, low, high]],
          renderItem: (_params: any, api: any) => {
            const x = api.coord([0, open])[0];
            const yOpen = api.coord([0, open])[1];
            const yClose = api.coord([0, spot])[1];
            const yLow = api.coord([0, low])[1];
            const yHigh = api.coord([0, high])[1];
            const bodyTop = Math.min(yOpen, yClose);
            const bodyHeight = Math.max(Math.abs(yClose - yOpen), 6);
            const bodyY = bodyTop - Math.max((6 - Math.abs(yClose - yOpen)) / 2, 0);
            const bodyWidth = 26;
            const bandWidth = 42;

            return {
              type: "group",
              children: [
                {
                  type: "rect",
                  shape: {
                    x: x - bandWidth / 2,
                    y: yHigh,
                    width: bandWidth,
                    height: Math.max(yLow - yHigh, 2),
                  },
                  style: {
                    fill: isBearish ? "rgba(239,68,68,0.10)" : "rgba(16,185,129,0.10)",
                  },
                },
                {
                  type: "line",
                  shape: {
                    x1: x,
                    y1: yHigh,
                    x2: x,
                    y2: yLow,
                  },
                  style: {
                    stroke: isBearish ? "rgba(239,68,68,0.88)" : "rgba(16,185,129,0.88)",
                    lineWidth: 2,
                  },
                },
                {
                  type: "rect",
                  shape: {
                    x: x - bodyWidth / 2,
                    y: bodyY,
                    width: bodyWidth,
                    height: bodyHeight,
                    r: 2,
                  },
                  style: {
                    fill: isBearish ? "rgba(239,68,68,0.88)" : "rgba(16,185,129,0.88)",
                    stroke: isBearish ? "#ef4444" : "#10b981",
                    lineWidth: 1.5,
                  },
                },
              ],
            };
          },
          z: 5,
        },
        {
          type: "custom",
          silent: true,
          data: [[0, spot]],
          renderItem: (_params: any, api: any) => {
            const ySpot = api.coord([0, spot])[1];
            return {
              type: "polygon",
              shape: {
                points: [
                  [4, ySpot],
                  [16, ySpot - 7],
                  [16, ySpot + 7],
                ],
              },
              style: {
                fill: "#fbbf24",
                stroke: "rgba(245,158,11,0.90)",
                lineWidth: 1,
                shadowBlur: 8,
                shadowColor: "rgba(245,158,11,0.70)",
              },
            };
          },
          z: 6,
        },
      ],
    };
  }, [
    close,
    high,
    low,
    open,
    resistanceCenter,
    resistanceZoneBot,
    resistanceZoneTop,
    spot,
    supportCenter,
    supportZoneBot,
    supportZoneTop,
    target1,
    target2,
  ]);

  return (
    <div style={{ display: "grid", gap: 12, width: "100%" }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          border: "1px solid rgba(255,255,255,0.06)",
          borderRadius: 10,
          overflow: "hidden",
        }}
      >
        {[
          { label: "Open", value: formatValue(open, 1), color: "#93c5fd", bold: false },
          { label: "High", value: formatValue(high, 1), color: "#34d399", bold: false },
          { label: "Low", value: formatValue(low, 1), color: "#f87171", bold: false },
          { label: "Spot", value: formatValue(spot, 1), color: "#fbbf24", bold: true },
          { label: "Support", value: formatValue(supportCenter, 0), color: "#34d399", bold: false },
          { label: "Resistance", value: formatValue(resistanceCenter, 0), color: "#f87171", bold: false },
        ].map((cell, index, cells) => (
          <div
            key={cell.label}
            style={{
              flex: "1 1 110px",
              minWidth: 0,
              display: "flex",
              flexDirection: "column",
              gap: 4,
              padding: "7px 10px",
              borderRight:
                index === cells.length - 1 ? "none" : "1px solid rgba(255,255,255,0.05)",
            }}
          >
            <div
              style={{
                fontSize: 9,
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                color: "#334155",
                fontFamily: "JetBrains Mono, monospace",
              }}
            >
              {cell.label}
            </div>
            <div
              style={{
                color: cell.color,
                fontSize: cell.bold ? 16 : 14,
                fontWeight: cell.bold ? 800 : 700,
                fontFamily: "JetBrains Mono, monospace",
              }}
            >
              {cell.value}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          borderRadius: 12,
          background: "rgba(4,8,16,0.50)",
          border: "1px solid rgba(255,255,255,0.04)",
          overflow: "hidden",
        }}
      >
        <ReactECharts
          option={option}
          notMerge={false}
          lazyUpdate={true}
          style={{ width: "100%", height: `${Math.max(320, height)}px` }}
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 8,
          marginTop: 10,
        }}
      >
        <div
          style={{
            background: "rgba(255,255,255,0.025)",
            border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: 10,
            padding: "8px 12px",
          }}
        >
          <div
            style={{
              fontSize: 9,
              textTransform: "uppercase",
              color: "#2a3d50",
              letterSpacing: "0.10em",
            }}
          >
            Trap Risk
          </div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#f59e0b" }}>
            {trapRisk.label}
            {trapRisk.pct > 0 ? ` · ${trapRisk.pct}%` : ""}
          </div>
        </div>

        <div
          style={{
            background: "rgba(255,255,255,0.025)",
            border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: 10,
            padding: "8px 12px",
          }}
        >
          <div
            style={{
              fontSize: 9,
              textTransform: "uppercase",
              color: "#2a3d50",
              letterSpacing: "0.10em",
            }}
          >
            Trap Type
          </div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#f87171" }}>{trapType}</div>
        </div>

        <div
          style={{
            background: "rgba(255,255,255,0.025)",
            border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: 10,
            padding: "8px 12px",
          }}
        >
          <div
            style={{
              fontSize: 9,
              textTransform: "uppercase",
              color: "#2a3d50",
              letterSpacing: "0.10em",
            }}
          >
            MSS Score
          </div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>
            {mssScore}
            {pressureLabel !== "-" ? ` · ${pressureLabel}` : ""}
          </div>
        </div>
      </div>
    </div>
  );
}
