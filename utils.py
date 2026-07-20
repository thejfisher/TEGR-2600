"""
TEGR 2600 Utilities
===================
Interpolation functions for bridging continuous particle coordinates
to the discrete FDTD torsion grid.

Used primarily by the pilot-wave (dBB) preset where particles are guided
by the spatial gradient of the Eulerian field at their exact (non-grid-
aligned) positions.
"""
import torch
import torch.nn.functional as F


def trilinear_interpolate(field, coords, grid_min, grid_max, grid_res):
    """
    Interpolate a 3-D scalar field at arbitrary continuous coordinates
    using PyTorch's grid_sample (trilinear mode).

    Parameters
    ----------
    field : torch.Tensor
        Shape ``(1, 1, D, H, W)`` - the Eulerian torsion grid.
    coords : torch.Tensor
        Shape ``(N, 3)`` - particle positions in *simulation* space.
    grid_min : float
        Lower bound of the grid in each axis.
    grid_max : float
        Upper bound of the grid in each axis.
    grid_res : int
        Number of grid cells per axis.

    Returns
    -------
    torch.Tensor
        Shape ``(N,)`` - interpolated scalar values at each coordinate.
    """
    norm = 2.0 * (coords - grid_min) / (grid_max - grid_min) - 1.0
    grid = norm.unsqueeze(0).unsqueeze(0).unsqueeze(0)
    sampled = F.grid_sample(
        field, grid,
        mode='bilinear', padding_mode='border', align_corners=True,
    )
    return sampled.squeeze()


def trilinear_interpolate_gradient(field, coords, grid_min, grid_max, grid_res, dx):
    """
    Compute the spatial gradient of *field* at arbitrary particle positions
    using central finite differences on the grid followed by trilinear
    interpolation.

    Parameters
    ----------
    field : torch.Tensor, shape (1, 1, D, H, W)
    coords : torch.Tensor, shape (N, 3)
    grid_min, grid_max : float
    grid_res : int
    dx : float  - grid spacing

    Returns
    -------
    torch.Tensor, shape (N, 3) - gradient (dphi/dx, dphi/dy, dphi/dz)
    """
    phi = field[0, 0]
    grad_x = torch.zeros_like(phi)
    grad_x[1:-1, :, :] = (phi[2:, :, :] - phi[:-2, :, :]) / (2.0 * dx)
    grad_y = torch.zeros_like(phi)
    grad_y[:, 1:-1, :] = (phi[:, 2:, :] - phi[:, :-2, :]) / (2.0 * dx)
    grad_z = torch.zeros_like(phi)
    grad_z[:, :, 1:-1] = (phi[:, :, 2:] - phi[:, :, :-2]) / (2.0 * dx)

    grad_field = torch.stack([grad_x, grad_y, grad_z], dim=0).unsqueeze(0)
    norm = 2.0 * (coords - grid_min) / (grid_max - grid_min) - 1.0
    # PyTorch grid_sample expects (x, y, z) to map to (W, H, D). Since our phi is (X, Y, Z),
    # we must pass [Z, Y, X] to grid_sample.
    grid = norm.flip(-1).unsqueeze(0).unsqueeze(0).unsqueeze(0)
    sampled = F.grid_sample(
        grad_field, grid,
        mode='bilinear', padding_mode='border', align_corners=True,
    )
    return sampled[0, :, 0, 0, :].T
