import torch
# import __init__
import sys
from icecream import ic


# import metamorphosis as mt
from . import classic as cl
from . import constrained as cn
from . import simplex as sp
from . import joined as jn

from ..utils import torchbox as tb
from ..utils.decorators import time_it


def commun_before(momentum_ini, source):
    if type(momentum_ini) in [int, float]:
        momentum_ini = momentum_ini * torch.ones(source.shape, device=source.device)
    momentum_ini.requires_grad = True

    return momentum_ini


def commun_after(mr, momentum_ini, safe_mode, n_iter, grad_coef):
    if not safe_mode:
        mr.forward(momentum_ini, n_iter=n_iter, grad_coef=grad_coef)
    else:
        mr.forward_safe_mode(momentum_ini, n_iter=n_iter, grad_coef=grad_coef)
    return mr


@time_it
def lddmm(
    source,
    target,
    momentum_ini,
    kernelOperator,
    cost_cst,
    integration_steps,
    n_iter,
    grad_coef,
    data_term=None,
    sharp=False,
    safe_mode=False,
    integration_method="semiLagrangian",
    dx_convention="pixel",
    optimizer_method="LBFGS_torch",
    hamiltonian_integration=False,
):
    """
    Perform a Large Deformation Diffeomorphic Metric Mapping (LDDMM) transformation between a source and a target.

    Parameters
    ----------
    # source : torch.Tensor
        Source image. [B,C,H,W] or [B, C, H, W, D]
    target : torch.Tensor
        Target image. [B,C,H,W] or [B, C, H, W, D]
    momentum_ini : torch.Tensor or float
        Initial momentum, the variable to optimize on. If float, will be broadcasted to the same shape as source.
    kernelOperator : callable
        Kernel operator for computing transformations.
    cost_cst : float
        Cost constant for regularization.
    integration_steps : int
        Number of integration steps.
    n_iter : int
        Number of iterations for optimization.
    grad_coef : float
        Gradient coefficient for optimization.
    data_term : optional
        Data term for optimization. must be a child of DataCost class.
    sharp : bool, optional
        If True, use "sharp" integration method.
    safe_mode : bool, optional
        If True, use safe mode for integration.
    integration_method : str, optional
        Integration method to use (default is "semiLagrangian").
    dx_convention : str, optional
        dx convention to use (default is "pixel").
    optimizer_method : str, optional
        Optimization method to use (default is "adadelta").

    Returns
    -------
    Metamorphosis_Shooting
        LDDMM shooting object after transformation.

    Examples
    --------
    .. code-block:: python

    """

    momentum_ini = commun_before(momentum_ini, source)
    if sharp:
        integration_method = "sharp"

    mp = cl.Metamorphosis_integrator(
        method=integration_method,
        rho=1,
        n_step=integration_steps,
        kernelOperator=kernelOperator,
        dx_convention=dx_convention,
    )
    mr = cl.Metamorphosis_Shooting(
        source,
        target,
        mp,
        cost_cst=cost_cst,
        # optimizer_method='LBFGS_torch',
        optimizer_method=optimizer_method,
        data_term=data_term,
        hamiltonian_integration=hamiltonian_integration,
    )

    mr = commun_after(mr, momentum_ini, safe_mode, n_iter, grad_coef)

    return mr


@time_it
def metamorphosis(
    source,
    target,
    momentum_ini,
    rho,
    cost_cst,
    integration_steps,
    n_iter,
    grad_coef,
    kernelOperator,
    data_term=None,
    sharp=False,
    safe_mode=True,
    integration_method="semiLagrangian",
    optimizer_method="LBFGS_torch",
    dx_convention="pixel",
    hamiltonian_integration=False,
):

    momentum_ini = commun_before(momentum_ini, source)
    if sharp:
        integration_method = "sharp"

    mp = cl.Metamorphosis_integrator(
        method=integration_method,
        rho=rho,
        kernelOperator=kernelOperator,
        n_step=integration_steps,
        dx_convention=dx_convention,
    )
    mr = cl.Metamorphosis_Shooting(
        source,
        target,
        mp,
        cost_cst=cost_cst,
        data_term=data_term,
        # optimizer_method='LBFGS_torch')
        optimizer_method=optimizer_method,
        hamiltonian_integration=hamiltonian_integration,
    )

    mr = commun_after(mr, momentum_ini, safe_mode, n_iter, grad_coef)
    return mr


# ==================================================
#  From contrained.py


@time_it
def weighted_metamorphosis(
    source,
    target,
    residual,
    residual_mask,
    kernelOperator,
    cost_cst,
    n_iter,
    grad_coef,
    data_term=None,
    sharp=False,
    safe_mode=True,
    optimizer_method="adadelta",
    dx_convention="pixel",
):
    print("plop")
    device = source.device
    #     sigma = tb.format_sigmas(sigma,len(source.shape[2:]))
    if type(residual) == int:
        residual = torch.zeros(source.shape, device=device)
    residual.requires_grad = True

    mp_weighted = cn.ConstrainedMetamorphosis_integrator(
        residual_mask=residual_mask,
        kernelOperator=kernelOperator,
        sharp=sharp,
        dx_convention=dx_convention,
    )
    mr_weighted = cn.ConstrainedMetamorphosis_Shooting(
        source,
        target,
        mp_weighted,
        cost_cst=cost_cst,
        optimizer_method=optimizer_method,
        data_term=data_term,
    )
    if not safe_mode:
        mr_weighted.forward(residual, n_iter=n_iter, grad_coef=grad_coef)
    else:
        mr_weighted.forward_safe_mode(residual, n_iter=n_iter, grad_coef=grad_coef)
    return mr_weighted


@time_it
def oriented_metamorphosis(
    source,
    target,
    residual,
    mp_orienting,
    mu,
    rho,
    gamma,
    sigma,
    cost_cst,
    n_iter,
    grad_coef,
    dx_convention="pixel",
):
    mask = mp_orienting.image_stock.to(source.device)
    orienting_field = mp_orienting.field_stock.to(source.device)
    if type(residual) == int:
        residual = torch.zeros(source.shape)
    residual.requires_grad = True

    # start = time.time()
    mp_orient = cn.ConstrainedMetamorphosis_integrator(
        orienting_mask=mask,
        orienting_field=orienting_field,
        mu=mu,
        rho=rho,
        gamma=gamma,
        sigma_v=(sigma,) * len(residual.shape),
        dx_convention=dx_convention,
        # n_step=20 # n_step is defined from mask.shape[0]
    )
    mr_orient = cn.ConstrainedMetamorphosis_Shooting(
        source,
        target,
        mp_orient,
        cost_cst=cost_cst,
        # optimizer_method='LBFGS_torch')
        optimizer_method="adadelta",
    )
    mr_orient.forward(residual, n_iter=n_iter, grad_coef=grad_coef)
    return mr_orient


@time_it
def constrained_metamorphosis(
    source,
    target,
    residual,
    mask_w,
    field_orienting,
    mask_o,
    kernelOperator,
    cost_cst,
    n_iter,
    grad_coef,
    sharp=False,
    dx_convention="pixel",
):
    if type(residual) == int:
        residual = torch.zeros(source.shape, device=source.device)
    residual.requires_grad = True

    # start = time.time()
    mp_constr = cn.ConstrainedMetamorphosis_integrator(
        orienting_mask=mask_o,
        orienting_field=field_orienting,
        residual_mask=mask_w,
        kernelOperator=kernelOperator,
        sharp=sharp,
        dx_convention=dx_convention,
        # n_step=20 # n_step is defined from mask.shape[0]
    )
    mr_constr = cn.ConstrainedMetamorphosis_Shooting(
        source, target, mp_constr, cost_cst=cost_cst, optimizer_method="LBFGS_torch"
    )
    # optimizer_method='adadelta')
    mr_constr.forward(residual, n_iter=n_iter, grad_coef=grad_coef)
    return mr_constr


def joined_metamorphosis(
    source_image,
    target_image,
    source_mask,
    target_mask,
    momentum_ini,
    rho,
    kernelOperator,
    data_term=None,
    dx_convention="pixel",
    n_step=10,
    n_iter=1000,
    grad_coef=2,
    cost_cst=0.001,
    plot=False,
    safe_mode=False,
):
    # source = torch.stack([source_image,source_mask],dim=1)
    # target = torch.stack([target_image,target_mask],dim=1)
    if type(momentum_ini) in [int, float]:
        shape = (1, 2) + source_image.shape[2:]
        momentum_ini = momentum_ini * torch.ones(
            shape, device=source_image.device, dtype=source_image.dtype
        )
    momentum_ini.requires_grad = True

    mp = jn.Weighted_joinedMask_Metamorphosis_integrator(
        rho=rho,
        kernelOperator=kernelOperator,
        n_step=n_step,
        dx_convention=dx_convention,
        # debug=True
    )
    mr = jn.Weighted_joinedMask_Metamorphosis_Shooting(
        source_image,
        target_image,
        source_mask,
        target_mask,
        mp,
        cost_cst=cost_cst,
        data_term=data_term,
        optimizer_method="LBFGS_torch",
        # optimizer_method='adadelta'
    )
    if safe_mode:
        mr.forward_safe_mode(momentum_ini, n_iter, grad_coef, plot)
    else:
        mr.forward(momentum_ini, n_iter=n_iter, grad_coef=grad_coef, plot=plot)
    return mr


def simplex_metamorphosis(
    source,
    target,
    momentum_ini,
    kernelOperator,
    rho,
    data_term,
    dx_convention="pixel",
    n_step=10,
    n_iter=1000,
    grad_coef=2,
    cost_cst=0.001,
    plot=False,
    safe_mode=False,
    ham=False,
):

    if type(momentum_ini) in [int, float]:
        momentum_ini = momentum_ini * torch.ones(
            source.shape, device=source.device, dtype=source.dtype
        )
    momentum_ini.requires_grad = True

    mp = sp.Simplex_sqrt_Metamorphosis_integrator(
        rho=rho,
        kernelOperator=kernelOperator,
        n_step=n_step,
        dx_convention=dx_convention,
        # debug=True
    )
    mr = sp.Simplex_sqrt_Shooting(
        source.clone(),
        target.clone(),
        mp,
        cost_cst=cost_cst,
        data_term=data_term,
        optimizer_method="LBFGS_torch",
        # optimizer_method='adadelta'
        hamiltonian_integration=ham,
    )
    if safe_mode:
        mr.forward_safe_mode(momentum_ini, n_iter, grad_coef, plot)
    else:
        mr.forward(momentum_ini, n_iter=n_iter, grad_coef=grad_coef, plot=plot)
    return mr
