"use client";
import React from "react";
import { MesiaData, MesiaParameters } from "../types";
import MesiaMultiWaveStudio from "../../MesiaMultiWaveStudio";

interface WaveStudioTabProps {
  data: MesiaData;
  parameters: MesiaParameters;
  onApplyParameters?: (updates: Partial<MesiaParameters>) => void;
}

export default function WaveStudioTab({
  data,
  parameters,
  onApplyParameters,
}: WaveStudioTabProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <MesiaMultiWaveStudio
        plotId={data.plot_id}
        initialSoilTexture={parameters.soilTexture}
        expertRole={parameters.expertPersona === "auditor" ? "all" : parameters.expertPersona}
        data={data}
        onApplyToObservatory={(updates: any) => {
          if (onApplyParameters && updates) {
            onApplyParameters({
              soilTexture: updates.soilTexture || parameters.soilTexture,
              antennaHeightM: updates.antennaHeightM || parameters.antennaHeightM,
              elevationMaskDeg: updates.elevationDeg || parameters.elevationMaskDeg,
            });
          }
        }}
      />
    </div>
  );
}
