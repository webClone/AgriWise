"use client";

import Masonry from "react-masonry-css";
import React from "react";

interface MasonryGridProps {
  children: React.ReactNode;
  breakpointCols?: { [key: number]: number; default: number };
}

export default function MasonryGrid({ 
  children, 
  breakpointCols = {
    default: 3,
    1100: 2,
    700: 1
  }
}: MasonryGridProps) {
  return (
    <Masonry
      breakpointCols={breakpointCols}
      // RTL Fix: Use negative margin-right on container, and padding-right on columns
      className="flex -mr-6 w-auto"
      columnClassName="pr-6 bg-clip-padding"
    >
      {/* 
        Wrap children to ensure consistent vertical spacing between items within a column.
        We use mb-6 to match the horizontal gutter (1.5rem = 24px).
      */}
      {React.Children.map(children, child => (
        <div className="mb-6">
          {child}
        </div>
      ))}
    </Masonry>
  );
}
