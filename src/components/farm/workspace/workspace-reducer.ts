import {
  createInitialWorkspaceState as createInitialWorkspaceStateImpl,
  workspaceReducer as workspaceReducerImpl,
} from "./workspace-reducer.mjs";
import type { WorkspaceState, WorkspaceAction, PlotScope } from "./workspace-types";

export function createInitialWorkspaceState(
  options?: Partial<PlotScope> & { initialTool?: string }
): WorkspaceState {
  return createInitialWorkspaceStateImpl(options);
}

export function workspaceReducer(
  state: WorkspaceState,
  action: WorkspaceAction
): WorkspaceState {
  return workspaceReducerImpl(state, action);
}
