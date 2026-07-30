/** Normalize persisted/live engine collections to the frontend's array contract. */
export function normalizeEngineCollection(
  value: unknown
): Record<string, unknown>[] {
  if (Array.isArray(value)) {
    return value.filter(
      (engine): engine is Record<string, unknown> =>
        engine !== null && typeof engine === "object" && !Array.isArray(engine)
    );
  }

  if (value !== null && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, engine]) => engine !== null && typeof engine === "object" && !Array.isArray(engine))
      .map(([id, engine]) => ({ id, ...(engine as Record<string, unknown>) }));
  }

  return [];
}
