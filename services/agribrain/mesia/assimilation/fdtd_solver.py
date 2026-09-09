"""MESIA 3D PyTorch FDTD Maxwell Solver.

Simulates exact EM wave propagation, diffraction, and scattering
through complex biological media (canopies, soils) using the Yee Algorithm.
"""

import torch
import torch.nn.functional as F
from typing import Tuple

class BiologicalPermittivityMap:
    """Maps ASMAE states to electrical permittivity and conductivity across radio frequencies."""

    @staticmethod
    def get_soil_properties(vwc: float, freq_hz: float = 2.4e9) -> Tuple[float, float]:
        """
        Unified soil dielectric model. Uses Peplinski & Dobson (1995) dispersion when
        frequency is in microwave bands, falling back to Topp equation for bulk low-frequency.
        
        vwc: Volumetric Water Content (0.0 to 1.0)
        freq_hz: Carrier frequency in Hz (default 2.4 GHz)
        Returns: (Relative Permittivity eps_r, Conductivity sigma S/m)
        """
        vwc = max(0.001, min(0.60, float(vwc)))
        if freq_hz >= 100e6:
            return BiologicalPermittivityMap.get_soil_properties_peplinski(vwc, freq_hz)
        
        # Topp's polynomial equation for LF (< 100 MHz)
        eps_r = 3.03 + 9.3 * vwc + 146.0 * (vwc ** 2) - 76.7 * (vwc ** 3)
        sigma = 0.001 + (vwc * 0.1)
        return float(eps_r), float(sigma)

    @staticmethod
    def invert_soil_permittivity_topp(eps_r: float) -> float:
        """
        Numerically inverts Topp's polynomial using Newton-Raphson to solve for VWC:
        eps_r = 3.03 + 9.3*w + 146*w^2 - 76.7*w^3
        """
        target_eps = max(3.25, min(45.0, float(eps_r)))
        vwc = 0.15  # Initial guess
        for _ in range(12):
            f_val = 3.03 + 9.3 * vwc + 146.0 * (vwc ** 2) - 76.7 * (vwc ** 3) - target_eps
            f_prime = 9.3 + 292.0 * vwc - 230.1 * (vwc ** 2)
            if abs(f_prime) < 1e-7:
                break
            delta = f_val / f_prime
            vwc -= delta
            vwc = max(0.02, min(0.60, vwc))
            if abs(delta) < 1e-6:
                break
        return float(vwc)

    @staticmethod
    def get_soil_properties_peplinski(
        vwc: float,
        freq_hz: float = 2.4e9,
        sand_frac: float = 0.45,
        clay_frac: float = 0.15,
        bulk_density_g_cm3: float = 1.40,
        solid_density_g_cm3: float = 2.66,
        temp_c: float = 20.0,
    ) -> Tuple[float, float]:
        """
        Peplinski & Dobson (1995) Semi-Empirical Complex Dielectric Model.
        Computes both real storage (eps') and imaginary loss (eps''), returning
        relative permittivity eps_r and equivalent conductivity sigma (S/m).
        """
        import math
        theta = max(0.001, min(0.60, float(vwc)))
        s = max(0.0, min(1.0, float(sand_frac)))
        c = max(0.0, min(1.0, float(clay_frac)))
        rho_b = max(0.8, min(2.0, float(bulk_density_g_cm3)))
        rho_s = max(2.0, min(3.0, float(solid_density_g_cm3)))

        # Physical parameters for water dielectric relaxation (Debye model)
        # Static permittivity of free water at temperature T
        eps_w0 = 87.74 - 0.40008 * temp_c + 9.398e-4 * (temp_c ** 2)
        eps_winf = 4.9
        # Relaxation time of free water (seconds)
        tau_w = (1.1109e-10 - 3.824e-12 * temp_c + 6.938e-14 * (temp_c ** 2)) / (2.0 * math.pi)

        omega = 2.0 * math.pi * freq_hz
        eps_fw_real = eps_winf + (eps_w0 - eps_winf) / (1.0 + (omega * tau_w) ** 2)
        eps_fw_imag = (omega * tau_w * (eps_w0 - eps_winf)) / (1.0 + (omega * tau_w) ** 2)

        # Soil solids dielectric constant
        eps_s = (1.01 + 0.44 * rho_s) ** 2 - 0.062

        # Peplinski texture empirical exponents
        beta_prime = 1.2748 - 0.519 * s - 0.152 * c
        beta_dprime = 1.33797 - 0.603 * s - 0.166 * c

        # Effective conductivity contribution to loss scales with moisture content
        sigma_eff = max(0.01, 0.0467 + 0.2204 * rho_b - 0.4111 * s + 0.6614 * c)
        eps_0 = 8.854187817e-12
        cond_loss = (sigma_eff / (2.0 * math.pi * eps_0 * freq_hz)) * (theta * (rho_s - rho_b) / rho_s)

        # Real and imaginary mixing (alpha = 0.65)
        alpha = 0.65
        eps_m_real = 1.0 + (rho_b / rho_s) * (eps_s ** alpha - 1.0) + (theta ** beta_prime) * (eps_fw_real ** alpha) - theta
        eps_prime = eps_m_real ** (1.0 / alpha)

        eps_dprime = ((theta ** beta_dprime) * (eps_fw_imag ** alpha)) ** (1.0 / alpha) + cond_loss
        eps_dprime = max(0.01, eps_dprime)

        # Equivalent conductivity: sigma = 2 * pi * f * eps_0 * eps''
        sigma_total = 2.0 * math.pi * freq_hz * eps_0 * eps_dprime

        return float(eps_prime), float(sigma_total)

    @staticmethod
    def get_canopy_properties(
        canopy_water: float,
        freq_hz: float = 2.4e9,
        leaf_area_index: float = 2.0,
    ) -> Tuple[float, float]:
        """
        Ulaby & El-Rayes vegetation dielectric model for crop canopies.
        Maps canopy water fraction (0.0 to 1.0) and LAI to bulk canopy permittivity and loss.
        """
        import math
        cw = max(0.0, min(1.0, float(canopy_water)))
        lai = max(0.1, min(8.0, float(leaf_area_index)))

        # Foliage volume fraction v_foliage ~ 0.001 * LAI
        v_foliage = 0.001 * lai
        # Leaf dielectric constant: eps_leaf ~ 1.5 + 30.0 * cw
        eps_leaf_real = 1.5 + 28.0 * cw
        eps_leaf_imag = 0.5 + 10.0 * cw * (freq_hz / 1e9) / 2.4

        # Bulk canopy dielectric constant via linear volume averaging with air (eps_air=1)
        eps_bulk_real = 1.0 + v_foliage * (eps_leaf_real - 1.0)
        eps_bulk_imag = v_foliage * eps_leaf_imag

        eps_0 = 8.854187817e-12
        sigma_canopy = 2.0 * math.pi * freq_hz * eps_0 * eps_bulk_imag
        return float(eps_bulk_real), float(max(1e-5, sigma_canopy))


class PyTorchFDTDEngine:
    """3D Yee-Grid FDTD Engine vectorized in PyTorch."""
    def __init__(self, nx: int, ny: int, nz: int, dx: float, dt: float):
        self.nx, self.ny, self.nz = nx, ny, nz
        self.dx = dx
        self.dt = dt
        
        # Physical constants
        self.mu_0 = 4.0 * torch.pi * 1e-7
        self.eps_0 = 8.854e-12
        
        # E and H fields [Batch, Channels, X, Y, Z]
        # We use a batch size of 1 and 1 channel per field component
        self.Ex = torch.zeros((1, 1, nx, ny, nz))
        self.Ey = torch.zeros((1, 1, nx, ny, nz))
        self.Ez = torch.zeros((1, 1, nx, ny, nz))
        
        self.Hx = torch.zeros((1, 1, nx, ny, nz))
        self.Hy = torch.zeros((1, 1, nx, ny, nz))
        self.Hz = torch.zeros((1, 1, nx, ny, nz))
        
        # Grid properties
        self.eps_r = torch.ones((1, 1, nx, ny, nz))
        self.sigma = torch.zeros((1, 1, nx, ny, nz))
        
        # Add simple absorbing boundary sponge layer to prevent reflections
        sponge_thickness = 5
        max_sigma = 0.5
        for i in range(sponge_thickness):
            sigma_val = max_sigma * ((sponge_thickness - i) / sponge_thickness)**2
            self.sigma[:,:,i,:,:] += sigma_val; self.sigma[:,:,-1-i,:,:] += sigma_val
            self.sigma[:,:,:,i,:] += sigma_val; self.sigma[:,:,:,-1-i,:] += sigma_val
            self.sigma[:,:,:,:,i] += sigma_val; self.sigma[:,:,:,:,-1-i] += sigma_val
        
    def set_soil_layer(self, z_start: int, vwc: float):
        """Creates a horizontal soil layer starting at z_start going down."""
        eps_val, sig_val = BiologicalPermittivityMap.get_soil_properties(vwc)
        self.eps_r[:, :, :, :, :z_start] = eps_val
        self.sigma[:, :, :, :, :z_start] = sig_val
        
    def step_time(self):
        """Advances the Maxwell curl equations by one dt."""
        # Update coefficients
        eps = self.eps_0 * self.eps_r
        
        # (1 - (sigma*dt)/(2*eps)) / (1 + (sigma*dt)/(2*eps))
        ca = (1.0 - (self.sigma * self.dt) / (2.0 * eps)) / (1.0 + (self.sigma * self.dt) / (2.0 * eps))
        cb = (self.dt / (eps * self.dx)) / (1.0 + (self.sigma * self.dt) / (2.0 * eps))
        
        da = 1.0  # Assuming mu_r = 1 and magnetic conductivity = 0
        db = self.dt / (self.mu_0 * self.dx)
        
        # We use torch.roll to compute spatial differences (curl)
        
        # Update E field
        # dHz/dy - dHy/dz
        curl_H_x = (self.Hz - torch.roll(self.Hz, shifts=1, dims=3)) - (self.Hy - torch.roll(self.Hy, shifts=1, dims=4))
        self.Ex = ca * self.Ex + cb * curl_H_x
        
        # dHx/dz - dHz/dx
        curl_H_y = (self.Hx - torch.roll(self.Hx, shifts=1, dims=4)) - (self.Hz - torch.roll(self.Hz, shifts=1, dims=2))
        self.Ey = ca * self.Ey + cb * curl_H_y
        
        # dHy/dx - dHx/dy
        curl_H_z = (self.Hy - torch.roll(self.Hy, shifts=1, dims=2)) - (self.Hx - torch.roll(self.Hx, shifts=1, dims=3))
        self.Ez = ca * self.Ez + cb * curl_H_z
        
        # Removed hard PEC boundary conditions to allow waves to enter sponge layer
        
        # Update H field
        curl_E_x = (torch.roll(self.Ez, shifts=-1, dims=3) - self.Ez) - (torch.roll(self.Ey, shifts=-1, dims=4) - self.Ey)
        self.Hx = da * self.Hx - db * curl_E_x
        
        curl_E_y = (torch.roll(self.Ex, shifts=-1, dims=4) - self.Ex) - (torch.roll(self.Ez, shifts=-1, dims=2) - self.Ez)
        self.Hy = da * self.Hy - db * curl_E_y
        
        curl_E_z = (torch.roll(self.Ey, shifts=-1, dims=2) - self.Ey) - (torch.roll(self.Ex, shifts=-1, dims=3) - self.Ex)
        self.Hz = da * self.Hz - db * curl_E_z
