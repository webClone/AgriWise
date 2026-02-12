import React from 'react';
import { YieldChart } from './YieldChart';
import { FieldHealthStats } from './FieldHealthStats';

interface ToolResultRendererProps {
  toolName: string;
  result: any;
}

export const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({ toolName, result }) => {
  if (!result || result.error) return null;

  switch (toolName) {
    case 'ml_predictYield':
      return <YieldChart data={result} />;
      
    case 'eo_getFieldIndicators':
      return <FieldHealthStats data={result} />;
      
    default:
      return (
        <div className="text-xs text-neutral-500 italic mt-1 bg-gray-50 p-2 rounded border">
            Topl Executed: {toolName} 
            <details>
                <summary>Raw Result</summary>
                <pre>{JSON.stringify(result, null, 2)}</pre>
            </details>
        </div>
      );
  }
};
