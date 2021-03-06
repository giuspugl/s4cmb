#!/usr/bin/python
"""
Module to handle instrument systematics.

Author: Julien Peloton, j.peloton@sussex.ac.uk
"""
from __future__ import division, absolute_import, print_function

import numpy as np

from s4cmb.systematics_f import systematics_f

arcsecond2rad = np.pi / 180. / 3600.
arcmin2rad = np.pi / 180. / 60.
deg2rad = np.pi / 180.

def inject_crosstalk_inside_SQUID(bolo_data, squid_ids, bolo_ids,
                                  mu=-3., sigma=1., radius=1, beta=2,
                                  seed=5438765, new_array=None,
                                  language='python'):
    """
    Introduce leakage between neighboring bolometers within a SQUID.
    You have to provide the list of bolometers, to which SQUID they
    belong, and the index of bolometers within each SQUID.

    Parameters
    ----------
    bolo_data : list of arrays
        Contains the time-ordered data of bolometers.
    squid_ids : list of strings
        Contains the SQUID id for each bolometer.
        Should have the same shape[0] as bolo_data.
    bolo_ids : list of strings
        Contains the positions of bolometers within their SQUID.
        Should have the same shape[0] as bolo_data.
    mu : float, optional
        Mean of the Gaussian used to generate the level of leakage,
        in percent. E.g. mu=1.0 means the leakage coefficients will be
        of order 1%.
    sigma : float, optional
        Width of the Gaussian used to generate the level of leakage,
        in percent. E.g. sigma=1.0 means the leakage coefficients will be
        of order X \pm 1%.
    radius : int, optional
        Controls the number of bolometers talking within a SQUID.
        radius=n means bolometers [N-n, N-n+1, ..., N, ..., N+n-1, N+n]
        will be crosstalking. `radius` must be at most equal to the number of
        bolometers within a SQUID.
    beta : int, optional
        Exponent controling the attenuation. The idea is that crosstalk depends
        on the separation length. Bolometer $b_i$ crosstalking with bolometers
        $b_{i \pm d}$ ($d \leq FF$) with leakage coefficients
        $\alpha_{i \pm d}$ will see his timestream modified as:
            $b_i = b_i + \dfrac{\alpha_{i \pm d}}{d^\beta}  b_{i \pm d}$.
        Assuming some fixed frequency spacing, hardware consideration
        suggests $\beta = 2$.
    seed : int, optional
        Control the random seed used to generate leakage coefficients.
    new_array : None or bolo_data-like array, optional
        If not None, return a new array of timestreams with the modifications.
        Modify bolo_data directly otherwise. Default is None.
    language : string, optional
        Language to perform computations to be chosen in ['python', 'fortran'].
        Default is python. [fortran is very slow...]

    Example
    ----------
    >>> from s4cmb.tod import load_fake_instrument
    >>> from s4cmb.tod import TimeOrderedDataPairDiff
    >>> inst, scan, sky_in = load_fake_instrument()
    >>> tod = TimeOrderedDataPairDiff(inst, scan, sky_in, CESnumber=0)
    >>> d = np.array([tod.map2tod(det) for det in range(2 * tod.npair)])
    >>> print(round(d[0][0], 3))
    40.95

    Inject crosstalk between neighbour bolometers (radius=1)
    >>> squid_ids = inst.focal_plane.get_indices('Sq')
    >>> bolo_ids = inst.focal_plane.bolo_index_in_squid
    >>> inject_crosstalk_inside_SQUID(d, squid_ids, bolo_ids, radius=1)
    >>> print(round(d[0][0], 3))
    39.561

    One can also keep the original timestreams, and return a new array
    containing modified timestreams.
    >>> d = np.array([tod.map2tod(det) for det in range(2 * tod.npair)])
    >>> d_new = np.zeros_like(d)
    >>> inject_crosstalk_inside_SQUID(d, squid_ids, bolo_ids, radius=1,
    ...     new_array=d_new, language='python')
    >>> print(round(d[0][0], 3), round(d_new[0][0], 3))
    ... #doctest: +NORMALIZE_WHITESPACE
    40.95 39.561

    For large number of bolometers per SQUID, you would prefer fortran
    to python to perform the loops. Choose python otherwise.
    """
    ## Make mu and sigma unitless (user provides percentage)
    mu = mu / 100.
    sigma = sigma / 100.

    combs = {}
    for bolo in range(len(bolo_data)):
        sq = squid_ids[bolo]
        if sq not in combs:
            combs[sq] = []
        combs[sq].append((bolo_ids[bolo], bolo))

    tsout = 0.0 + bolo_data
    # How much to leak from one bolometer to its neighboring channels
    state = np.random.RandomState(seed)
    cross_amp = state.normal(mu, sigma, len(bolo_data))

    if language == 'python':
        for sq in combs:
            for ch, i in combs[sq]:
                for ch2, i2 in combs[sq]:
                    separation_length = abs(ch - ch2)
                    if separation_length > 0 and separation_length <= radius:
                        tsout[i] += cross_amp[i2] / \
                            separation_length**beta * tsout[i2]

    elif language == 'fortran':
        ## F2PY convention
        tsout = np.array(tsout, order='F')
        for sq in combs:
            local_indices = np.array(combs[sq]).flatten()[:: 2]
            global_indices = np.array(combs[sq]).flatten()[1:: 2]
            systematics_f.inject_crosstalk_inside_squid_f(
                tsout, local_indices, global_indices,
                radius, cross_amp, beta,
                len(local_indices), len(bolo_data), len(bolo_data[0]))

    if new_array is not None:
        new_array[:] = tsout
    else:
        bolo_data[:] = tsout

def inject_crosstalk_SQUID_to_SQUID(bolo_data, squid_ids, bolo_ids,
                                    mu=-3., sigma=1.,
                                    squid_attenuation=100.,
                                    seed=5438765, new_array=None):
    """
    Introduce leakage between bolometers from different SQUIDs.
    You have to provide the list of bolometers, to which SQUID they
    belong, and the index of bolometers within each SQUID.

    Parameters
    ----------
    bolo_data : list of arrays
        Contains the time-ordered data of bolometers.
    squid_ids : list of strings
        Contains the SQUID id for each bolometer.
        Should have the same shape[0] as bolo_data.
    bolo_ids : list of strings
        Contains the positions of bolometers within their SQUID.
        Should have the same shape[0] as bolo_data.
    mu : float, optional
        Mean of the Gaussian used to generate the level of leakage,
        in percent. E.g. mu=1.0 means the leakage coefficients will be
        of order 1%.
    sigma : float, optional
        Width of the Gaussian used to generate the level of leakage,
        in percent. E.g. sigma=1.0 means the leakage coefficients will be
        of order X \pm 1%.
    squid_attenuation : int, optional
        Value controling the attenuation due to distance between SQUIDS.
        The idea is that crosstalk depends on the separation
        length between SQUIDs. Bolometer $b_i$ crosstalking with bolometers
        $b_{j}$ with leakage coefficients
        $\alpha_{j}$ will see his timestream modified as:
            $b_i = b_i + \dfrac{\alpha_{j}}{squid_attenuation}  b_{j}$.
        Default is 100.
    seed : int, optional
        Control the random seed used to generate leakage coefficients.
    new_array : None or bolo_data-like array, optional
        If not None, return a new array of timestreams with the modifications.
        Modify bolo_data directly otherwise. Default is None.

    Example
    ----------
    >>> from s4cmb.tod import load_fake_instrument
    >>> from s4cmb.tod import TimeOrderedDataPairDiff
    >>> inst, scan, sky_in = load_fake_instrument(nsquid_per_mux=4)
    >>> tod = TimeOrderedDataPairDiff(inst, scan, sky_in, CESnumber=0)
    >>> d = np.array([tod.map2tod(det) for det in range(2 * tod.npair)])
    >>> print(round(d[0][0], 3))
    40.948

    Inject crosstalk between bolometers in different SQUIDs
    >>> squid_ids = inst.focal_plane.get_indices('Sq')
    >>> bolo_ids = inst.focal_plane.bolo_index_in_squid
    >>> inject_crosstalk_SQUID_to_SQUID(d, squid_ids, bolo_ids,
    ...     squid_attenuation=100.)
    >>> print(round(d[0][0], 3))
    40.694

    One can also keep the original timestreams, and return a new array
    containing modified timestreams.
    >>> d = np.array([tod.map2tod(det) for det in range(2 * tod.npair)])
    >>> d_new = np.zeros_like(d)
    >>> inject_crosstalk_SQUID_to_SQUID(d, squid_ids, bolo_ids,
    ...     squid_attenuation=100., new_array=d_new)
    >>> print(round(d[0][0], 3), round(d_new[0][0], 3))
    ... #doctest: +NORMALIZE_WHITESPACE
    40.948 40.694

    """
    ## Make mu and sigma unitless (user provides percentage)
    mu = mu / 100.
    sigma = sigma / 100.

    combs = {}
    for bolo in range(len(bolo_data)):
        sq = squid_ids[bolo]
        if sq not in combs:
            combs[sq] = []
        combs[sq].append((bolo_ids[bolo], bolo))

    tsout = 0.0 + bolo_data
    # How much to leak from one bolometer to its neighboring channels
    state = np.random.RandomState(seed)
    cross_amp = state.normal(mu, sigma, len(bolo_data))

    ## Take one squid
    for sq1 in combs:
        ## Take all bolometers in that SQUID
        for ch, i in combs[sq1]:
            ## Take a second SQUID
            for sq2 in combs:
                if sq2 == sq1:
                    continue
                ## Take all bolometers in that SQUID
                for ch2, i2 in combs[sq2]:
                    tsout[i] += cross_amp[i2] / squid_attenuation * tsout[i2]

    if new_array is not None:
        new_array[:] = tsout
    else:
        bolo_data[:] = tsout

def modify_beam_offsets(bolometer_xpos, bolometer_ypos,
                        mu_diffpointing=10., sigma_diffpointing=5., seed=5847):
    """
    Modify the beam offsets (inject differential pointing between
    two pixel-pair bolometers). The model is the following:
    * Draw from a normal distribution G(mu, sigma)
      the magnitudes of the differential pointing rho.
    * Draw from a uniform distribution U(0, 2pi) the directions
      of the differential pointing theta.
    * Move the position of bottom bolometers as
      - x_top/bottom = \pm rho / 2 * cos(theta)
      - y_top/bottom = \pm rho / 2 * sin(theta)

    Parameters
    ----------
    bolometer_xpos : 1d array
        Initial beam centroid positions along the x axis. In radian.
    bolometer_ypos : 1d array
        Initial beam centroid positions along the y axis. In radian.
    mu_diffpointing : float, optional
        Mean of the distribution for differential pointing in arcsecond.
    sigma_diffpointing : float, optional
        Width of the distribution for differential pointing in arcsecond.
    seed : int, optional
        Random seed to control numbers generation.

    Returns
    ----------
    bolometer_xpos : 1d array
        Modified beam centroid positions along the x axis. In radian.
    bolometer_ypos : 1d array
        Modified beam centroid positions along the y axis. In radian.

    Examples
    ----------
    Inject differential pointing with magnitude 10 arcmin +- 5 arcmin.
    (completely irrealistic! just for test purposes).
    >>> bolometer_xpos = np.array([1., 1., -1., -1.]) * np.pi / 180.
    >>> bolometer_ypos = np.array([1., -1., -1., 1.]) * np.pi / 180.
    >>> x, y = modify_beam_offsets(bolometer_xpos, bolometer_ypos,
    ...     mu_diffpointing=600., sigma_diffpointing=300., seed=5847)
    >>> print(x * 180 / np.pi, y * 180 / np.pi) #doctest: +NORMALIZE_WHITESPACE
    [ 1.03802729  0.96197271 -1.02689298 -0.97310702]
    [ 0.92369044 -0.92369044 -1.10310547  1.10310547]

    """
    assert len(bolometer_xpos) == len(bolometer_ypos), \
        ValueError("x and y bolometer coordinates should have the same length")
    state = np.random.RandomState(seed)

    npair = int(len(bolometer_xpos) / 2)

    ## rho is defined by the user [xpos, ypos in radians - convert it!]
    rho = state.normal(mu_diffpointing * arcsecond2rad,
                       sigma_diffpointing * arcsecond2rad,
                       npair)

    ## Angle are uniformly drawn from 0 and 360 degree
    theta = state.uniform(0, 360, npair) * deg2rad

    rhox = rho / 2. * np.cos(theta)
    rhoy = rho / 2. * np.sin(theta)

    bolometer_xpos[::2] += rhox
    bolometer_xpos[1::2] += -rhox
    bolometer_ypos[::2] += rhoy
    bolometer_ypos[1::2] += -rhoy

    return bolometer_xpos, bolometer_ypos

def modify_pointing_parameters(values, errors):
    """
    This routine is not realistic at all for the moment!

    Parameters
    ----------
    values : 1d array
        Array containing values of the pointing parameters in degree.
    errors : 1d array
        Array containing values of the pointing parameter errors in degree.

    Returns
    ----------
    values_mod : 1d array
        Array containing modified values of the pointing parameters in degree.

    """
    values_mod = [p + err for p, err in zip(values, errors)]
    return values_mod


if __name__ == "__main__":
    import doctest
    doctest.testmod()
