"""
Ensemble Kalman Smoother (Rauch-Tung-Striebel).
Runs backward pass over Kalman filter history to compute smoothed states and covariances.
"""
import numpy as np
from typing import List, Tuple

class RTSSmoother:
    def __init__(self):
        pass

    def smooth(
        self,
        states_pred: List[np.ndarray],  # length T list of (N_STATES,)
        covs_pred: List[np.ndarray],    # length T list of (N_STATES, N_STATES)
        states_upd: List[np.ndarray],   # length T list of (N_STATES,)
        covs_upd: List[np.ndarray]      # length T list of (N_STATES, N_STATES)
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Executes the RTS backward smoothing pass.
        x_smooth_t = x_upd_t + C_t * (x_smooth_t+1 - x_pred_t+1)
        P_smooth_t = P_upd_t + C_t * (P_smooth_t+1 - P_pred_t+1) * C_t.T
        Where C_t = P_upd_t * inv(P_pred_t+1)
        """
        T = len(states_upd)
        if T == 0:
            return [], []

        # Smooth output lists
        states_smooth = [np.zeros_like(x) for x in states_upd]
        covs_smooth = [np.zeros_like(p) for p in covs_upd]

        # The last step T-1 smoothed is just the last updated step
        states_smooth[T - 1] = states_upd[T - 1].copy()
        covs_smooth[T - 1] = covs_upd[T - 1].copy()

        # Iterate backwards from T-2 down to 0
        for t in range(T - 2, -1, -1):
            x_upd = states_upd[t]
            P_upd = covs_upd[t]
            
            x_pred_next = states_pred[t + 1]
            P_pred_next = covs_pred[t + 1]
            
            x_smooth_next = states_smooth[t + 1]
            P_smooth_next = covs_smooth[t + 1]

            # Invert P_pred_next safely using pseudoinverse
            try:
                P_pred_inv = np.linalg.pinv(P_pred_next)
            except np.linalg.LinAlgError:
                # Fallback if inversion fails
                P_pred_inv = np.eye(P_pred_next.shape[0]) * 10.0

            # Smoother gain: C_t = P_upd * P_pred_inv
            C_t = P_upd @ P_pred_inv

            # Smoothed state
            state_diff = x_smooth_next - x_pred_next
            states_smooth[t] = x_upd + C_t @ state_diff

            # Smoothed covariance
            cov_diff = P_smooth_next - P_pred_next
            covs_smooth[t] = P_upd + C_t @ cov_diff @ C_t.T

        return states_smooth, covs_smooth
