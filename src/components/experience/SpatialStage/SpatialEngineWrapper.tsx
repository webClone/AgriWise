"use client";

import dynamic from "next/dynamic";

const SpatialEngine = dynamic(
  () => import("./SpatialEngine"),
  { ssr: false }
);

export default function SpatialEngineWrapper() {
  return <SpatialEngine />;
}
