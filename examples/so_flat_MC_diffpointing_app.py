## This examples describes how to use some basic functionalities
## of s4cmb such as:
## * simulate an input sky
## * simulate an instrument
## * simulate a scanning strategy
## * simulate TOD from the 3 previous guys
## * project back your TOD to sky maps.
from __future__ import division, absolute_import, print_function

## Initialise MPI
from mpi4py import MPI

## Import modules and routines
from s4cmb.input_sky import HealpixFitsMap

from s4cmb.instrument import Hardware

from s4cmb.scanning_strategy import ScanningStrategy

from s4cmb.tod import TimeOrderedDataPairDiff
from s4cmb.tod import OutputSkyMap

from s4cmb.config_s4cmb import NormaliseParser

from s4cmb.systematics import modify_beam_offsets

## Other packages needed
import os
import healpy as hp
import numpy as np
import argparse
import ConfigParser

def safe_mkdir(path):
    """
    Create a path and catch the race condition
    between path exists and mkdir.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

def addargs(parser):
    """ Parse command line arguments for s4cmb """

    ## Defaults args - load instrument, scan and sky parameters
    parser.add_argument(
        '-inifile', dest='inifile',
        required=True,
        help='Configuration file with parameter values.')
    parser.add_argument(
        '-tag', dest='tag',
        required=True,
        help='Tag name to identify your run. E.g. run_0_nosystematic.')

    ## You can also pass any new arguments, or even overwrite those
    ## from the ini file.
    parser.add_argument(
        '-input_filename', dest='input_filename',
        required=True, nargs='+',
        help='Input fits with alms.')
    parser.add_argument(
        '-array_noise_seed', dest='array_noise_seed',
        required=True, type=int,
        help='Seed to generate noise.')
    parser.add_argument(
        '-sim_number', dest='sim_number',
        required=True, type=int,
        help='Number of the sim.')
    parser.add_argument(
        '-folder_out', dest='folder_out',
        required=True,
        help='Name of the output folder.')
    parser.add_argument(
        '-nside_in', dest='nside_in',
        required=True, type=int,
        help='Name of the output folder.')
    parser.add_argument(
        '-fwhm_in', dest='fwhm_in',
        required=True, type=float,
        help='Name of the output folder.')

    parser.add_argument(
        '-mu_diffpointing', dest='mu_diffpointing',
        required=True, type=float,
        help='Magnitude of the differential pointing (arcsecond).')
    parser.add_argument(
        '-sigma_diffpointing', dest='sigma_diffpointing',
        required=True, type=float,
        help='Width of the differential pointing (arcsecond).')
    parser.add_argument(
        '-seed_diffpointing', dest='seed_diffpointing',
        required=True, type=int,
        help='Seed to generate differential pointing.')


if __name__ == "__main__":
    """
    Launch the pipeline!
    """
    parser = argparse.ArgumentParser(
        description='MPI version of s4cmb')
    addargs(parser)
    args = parser.parse_args(None)

    Config = ConfigParser.ConfigParser()
    Config.read(args.inifile)
    params = NormaliseParser(Config._sections['s4cmb'])

    ## Overwrite ini file params with params pass to the App directly
    for key in args.__dict__.keys():
        new = getattr(args, key)
        if key in params.__dict__.keys():
            old = getattr(params, key)
            if new in [None, 'None'] and old is not None:
                continue
            else:
                print("Overwriting {} with new value: {} -> {}".format(
                    key, old, new))

        setattr(params, key, new)

    rank = MPI.COMM_WORLD.rank
    size = MPI.COMM_WORLD.size

    if rank == 0:
        safe_mkdir(params.folder_out)

    print('sim [{}]'.format(params.sim_number),
          params.input_filename,
          params.array_noise_seed)

    ##################################################################
    ## START OF THE SIMULATION
    ## Flow is the following:
    ##   sky -> instrument -> scanning strategy ->
    ##      MAP2TOD -> (systematics) -> TOD2MAP
    ##################################################################
    ## Initialise our input maps
    sky_in = HealpixFitsMap(params.input_filename,
                            fwhm_in=params.fwhm_in,
                            nside_in=params.nside_in,
                            map_seed=params.map_seed,
                            do_pol=params.do_pol,
                            verbose=params.verbose,
                            no_ileak=params.no_ileak,
                            no_quleak=params.no_quleak)

    ## Initialise our instrument
    inst = Hardware(ncrate=params.ncrate,
                    ndfmux_per_crate=params.ndfmux_per_crate,
                    nsquid_per_mux=params.nsquid_per_mux,
                    npair_per_squid=params.npair_per_squid,
                    fp_size=params.fp_size,
                    fwhm=params.fwhm,
                    beam_seed=params.beam_seed,
                    projected_fp_size=params.projected_fp_size,
                    pm_name=params.pm_name,
                    type_hwp=params.type_hwp,
                    freq_hwp=params.freq_hwp,
                    angle_hwp=params.angle_hwp,
                    verbose=params.verbose)

    ## Initialize our scanning strategy
    scan = ScanningStrategy(nces=params.nces,
                            start_date=params.start_date,
                            telescope_longitude=params.telescope_longitude,
                            telescope_latitude=params.telescope_latitude,
                            telescope_elevation=params.telescope_elevation,
                            name_strategy=params.name_strategy,
                            sampling_freq=params.sampling_freq,
                            sky_speed=params.sky_speed,
                            ut1utc_fn=params.ut1utc_fn,
                            language=params.language)
    scan.run()

    ## Let's inject differential pointing between
    ## two pixel-pair bolometers in our data!
    ## The model is the following:
    ## * Draw from a normal distribution G(mu, sigma)
    ##      the magnitudes of the differential pointing rho.
    ## * Draw from a uniform distribution U(0, 2pi) the directions
    ##      of the differential pointing theta.
    ## * Move the position of bottom bolometers as
    ##      - x_top/bottom = \pm rho / 2 * cos(theta)
    ##      - y_top/bottom = \pm rho / 2 * sin(theta)
    ## et voila!
    inst.beam_model.xpos, inst.beam_model.ypos = \
        modify_beam_offsets(inst.beam_model.xpos,
                            inst.beam_model.ypos,
                            mu_diffpointing=args.mu_diffpointing,
                            sigma_diffpointing=args.sigma_diffpointing,
                            seed=args.seed_diffpointing)

    ## Let's now generate our TOD from our input sky, instrument,
    ## and scanning strategy.
    if params.verbose:
        print("Proc [{}] doing scans".format(rank), range(
            rank, scan.nces, size))

    state_for_noise = np.random.RandomState(params.array_noise_seed)
    seeds_for_noise = state_for_noise.randint(0, 1e6, scan.nces)
    for pos_CES, CESnumber in enumerate(range(rank, scan.nces, size)):
        if params.verbose:
            print("Proc [{}] with seeds ".format(rank),
                  seeds_for_noise[CESnumber], seeds_for_noise)
        tod = TimeOrderedDataPairDiff(
            inst, scan, sky_in,
            CESnumber=CESnumber,
            projection=params.projection,
            nside_out=params.nside_out,
            pixel_size=params.pixel_size,
            width=params.width,
            array_noise_level=params.array_noise_level,
            array_noise_seed=seeds_for_noise[CESnumber],
            mapping_perpair=True)

        ## Initialise map containers for each processor
        if pos_CES == 0:
            sky_out_tot = OutputSkyMap(projection=tod.projection,
                                       nside=tod.nside_out,
                                       obspix=tod.obspix,
                                       npixsky=tod.npixsky,
                                       pixel_size=tod.pixel_size)

        ## Scan input map to get TODs with original beam offsets
        for pair in tod.pair_list:
            d = np.array([
                tod.map2tod(det) for det in pair])

            ## Project TOD to maps with modified beam offsets
            tod.tod2map(d, sky_out_tot)

    MPI.COMM_WORLD.barrier()

    ## Coaddition over all processors.
    ## Note that all processors will then have the coadded data.
    ## If you want informations at the level of each CES (or group of),
    ## use instead:
    ## final_map = OutputSkyMap(nside=nside_out, obspix=tod.obspix)
    ## final_map.coadd_MPI(sky_out_tot, MPI=MPI)
    sky_out_tot.coadd_MPI(sky_out_tot, MPI=MPI)

    if rank == 0:
        name_out = '{}_{}_{}'.format(params.tag,
                                     params.name_instrument,
                                     params.name_strategy)
        sky_out_tot.pickle_me(
            '{}/sim{:03d}_{}.pkl'.format(
                args.folder_out, args.sim_number, name_out),
            shrink_maps=False, crop_maps=2**12,
            epsilon=0., verbose=False)

    MPI.COMM_WORLD.barrier()
