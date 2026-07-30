import sys
sys.path.append('.')
import numpy as np
import math
from scripts.v39_subpixel_calibration_natural_probe import execute_sub_experiment, OFFSETS_CALIBRATION, OFFSETS_VALIDATION, DEFAULT_POLYGON

res = execute_sub_experiment(
    '2026-05-27', 
    DEFAULT_POLYGON, 
    200.0, 
    10.0, 
    OFFSETS_CALIBRATION + OFFSETS_VALIDATION, 
    128, 
    128, 
    dry_run=False
)

grids = res['grids_object']
selected_conv = res['selected_sign_convention']
sign_multiplier = 1.0 if selected_conv == 'A' else -1.0
cal_grids = [g for g in grids if (g.requested_east_m, g.requested_north_m) in OFFSETS_CALIBRATION]
val_grids = [g for g in grids if (g.requested_east_m, g.requested_north_m) in OFFSETS_VALIDATION]

expected_cal = []
raw_est_cal = []
for g in cal_grids:
    # Exclude boundary offset of 5.0m
    if abs(g.requested_east_m) + abs(g.requested_north_m) < 1e-9 or abs(g.requested_east_m) >= 5.0 or abs(g.requested_north_m) >= 5.0:
        continue
    exp_dx = g.expected_dx_px_conv_a
    exp_dy = g.expected_dy_px_conv_a
    expected_cal.append([exp_dx, exp_dy])
    raw_dx = g.estimated_dx_px * sign_multiplier
    raw_dy = g.estimated_dy_px * sign_multiplier
    raw_est_cal.append([raw_dx, raw_dy])

X = np.array(raw_est_cal)
Y = np.array(expected_cal)

# Fit Ridge without bias: min ||Y - X * W||^2 + reg * ||W - I||^2
reg = 0.01
XTX = X.T @ X
I2 = np.eye(2)
Z = Y - X
W_diff = np.linalg.inv(XTX + reg * I2) @ X.T @ Z
A_cal = I2 + W_diff.T
b_cal = np.zeros(2)

print('A (strictly subpixel, no bias):', A_cal)
print('b:', b_cal)

print('\nValidation Set Calibration Results:')
raw_errs = []
cal_errs = []
for g in val_grids:
    exp_dx = g.expected_dx_px_conv_a
    exp_dy = g.expected_dy_px_conv_a
    raw_dx = g.estimated_dx_px * sign_multiplier
    raw_dy = g.estimated_dy_px * sign_multiplier
    raw_vec = np.array([raw_dx, raw_dy])
    
    # Apply subpixel-gated calibration (only if raw estimated shift is <= 0.5 pixels)
    if np.linalg.norm(raw_vec) <= 0.5:
        cal_vec = A_cal @ raw_vec + b_cal
    else:
        cal_vec = raw_vec
        
    raw_err = np.linalg.norm(raw_vec - np.array([exp_dx, exp_dy])) * 10.0
    cal_err = np.linalg.norm(cal_vec - np.array([exp_dx, exp_dy])) * 10.0
    raw_errs.append(raw_err**2)
    cal_errs.append(cal_err**2)
    print(f'{g.label:30} Expected A: ({exp_dx:+.3f}, {exp_dy:+.3f}) | Raw err: {raw_err:.3f}m | Cal Vec: ({cal_vec[0]:+.3f}, {cal_vec[1]:+.3f}) | Cal err: {cal_err:.3f}m')

print(f'\nRaw RMSE: {math.sqrt(np.mean(raw_errs)):.3f}m')
print(f'Calibrated RMSE: {math.sqrt(np.mean(cal_errs)):.3f}m')
print(f'Improvement: {((math.sqrt(np.mean(raw_errs)) - math.sqrt(np.mean(cal_errs))) / math.sqrt(np.mean(raw_errs)) * 100):.1f}%')
