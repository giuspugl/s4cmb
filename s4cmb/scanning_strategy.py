#!/usr/bin/python
"""
Script to simulate the scan of a CMB experiment.

Author: Julien Peloton, j.peloton@sussex.ac.uk
"""
from __future__ import division, absolute_import, print_function

import os
import ephem
import numpy as np
import healpy as hp
import weave

from s4cmb.scanning_strategy_f import scanning_strategy_f

from pyslalib import slalib

## numerical constants
radToDeg = 180. / np.pi
sidDayToSec = 86164.0905

class ScanningStrategy():
    """ Class to handle the scanning strategy of the telescope """
    def __init__(self, nces=12, start_date='2013/1/1 00:00:00',
                 telescope_longitude='-67:46.816',
                 telescope_latitude='-22:56.396', telescope_elevation=5200.,
                 name_strategy='deep_patch', sampling_freq=30., sky_speed=0.4,
                 ut1utc_fn='s4cmb/data/ut1utc.ephem', language='python'):
        """
        A scanning strategy consists in defining the site of observation
        on earth for which we will make the observation, the region
        of the sky to observe, and the schedule of observations.

        Parameters
        ----------
        nces : int, optional
            Number of scans to generate.
        start_date : string, optional
            Starting date for observations. The format is: YYYY/M/D HH:MM:SS.
        telescope_longitude : string, optional
            Longitute (angle) of the telescope. String form: 0:00:00.0.
        telescope_latitude : string, optional
            Latitude (angle) of the telescope. String form: 0:00:00.0.
        telescope_elevation : float, optional
            Height above sea level (in meter).
        name_strategy : string, optional
            Name of a pre-defined scanning strategy to define the boundaries
            of the scan: elevation, azimuth, and time. Only available for the:
            moment name_strategy = deep_patch.
        sampling_freq : float, optional
            Sampling frequency of the bolometers in Hz.
        sky_speed : float, optional
            Azimuth speed of the telescope in deg/s.
        ut1utc_fn : string, optional
            File containing time correction to UTC.
            This is not used here, but pass to the pointing module later on.
        language : string, optional
            Language used for core computations. For big experiments, the
            computational time can be big, and some part of the code can be
            speeded up by interfacing python with C or Fortran.
            Default is python (i.e. no interfacing and can be slow).
            Choose language=C or language=fortran otherwise. Note that C codes
            are compiled on-the-fly (weave), but for fortran codes you need
            first to compile it. See the setup.py or the provided Makefile.

        """
        self.nces = nces
        self.start_date = start_date
        self.name_strategy = name_strategy
        self.sampling_freq = sampling_freq
        self.sky_speed = sky_speed
        self.language = language
        self.ut1utc_fn = ut1utc_fn

        self.telescope_location = self.define_telescope_location(
            telescope_longitude, telescope_latitude, telescope_elevation)

        self.define_boundary_of_scan()

    def define_telescope_location(self, telescope_longitude='-67:46.816',
                                  telescope_latitude='-22:56.396',
                                  telescope_elevation=5200.):
        """
        Routine to define the site of observation on earth for which
        positions are to be computed. The location of the Polarbear telescope
        is entered as default.

        Parameters
        ----------
        telescope_longitude : str
            Longitute (angle) of the telescope. String form: 0:00:00.0.
        telescope_latitude : str
            Latitude (angle) of the telescope. String form: 0:00:00.0.
        telescope_elevation : float
            Height above sea level (in meter).

        Returns
        ----------
        location : Observer instance
            An `Observer` instance allows you to compute the positions of
            celestial bodies as seen from a particular latitude and longitude
            on the Earth's surface.

        Examples
        ----------
        >>> scan = ScanningStrategy()
        >>> telescope_location = scan.define_telescope_location()
        >>> telescope_location.elevation
        5200.0

        """
        location = ephem.Observer()
        location.long = telescope_longitude
        location.lat = telescope_latitude
        location.elevation = telescope_elevation

        return location

    def define_boundary_of_scan(self):
        """
        Given a pre-defined scanning strategy,
        define the boundaries of the scan: elevation, azimuth, and time.
        For a custom usage (advanced users), modify this routine.

        Examples
        ----------
        >>> scan = ScanningStrategy(name_strategy='deep_patch')
        >>> scan.elevation # doctest: +NORMALIZE_WHITESPACE
        [30.0, 45.5226, 47.7448, 49.967,
         52.1892, 54.4114, 56.6336, 58.8558,
         61.078, 63.3002, 65.5226, 35.2126]

        Only the observation of a deep patch (5 percent of the sky
        in the southern hemisphere) is currently available.
        >>> scan = ScanningStrategy(name_strategy='toto')
        ... # doctest: +NORMALIZE_WHITESPACE, +ELLIPSIS
        Traceback (most recent call last):
         ...
        ValueError: Only name_strategy = deep_patch is currently available.
        For a custom usage (advanced users), modify this routine.

        >>> scan.allowed_scanning_strategies
        ['deep_patch']
        """
        self.allowed_scanning_strategies = ['deep_patch']

        if self.name_strategy == 'deep_patch':
            self.elevation = [30.0, 45.5226, 47.7448, 49.967,
                              52.1892, 54.4114, 56.6336, 58.8558,
                              61.078, 63.3002, 65.5226, 35.2126]

            self.az_min = [134.2263, 162.3532, 162.3532, 162.3532,
                           162.3532, 162.3532, 162.3532, 162.3532,
                           162.3532, 162.3532, 162.3532, 204.7929]

            self.az_max = [154.2263, 197.3532, 197.3532, 197.3532,
                           197.3532, 197.3532, 197.3532, 197.3532,
                           197.3532, 197.3532, 197.3532, 224.7929]

            self.begin_LST = ['17:07:54.84', '22:00:21.76', '22:00:21.76',
                              '22:00:21.76', '22:00:21.76', '22:00:21.76',
                              '22:00:21.76', '22:00:21.76', '22:00:21.76',
                              '22:00:21.76', '22:00:21.76', '2:01:01.19']

            self.end_LST = ['22:00:21.76', '02:01:01.19', '02:01:01.19',
                            '02:01:01.19', '02:01:01.19', '02:01:01.19',
                            '02:01:01.19', '02:01:01.19', '02:01:01.19',
                            '02:01:01.19', '02:01:01.19', '6:53:29.11']

            ## Center of the patch in RA/Dec
            self.ra_mid = 0.
            self.dec_mid = -57.5
        else:
            raise ValueError("Only name_strategy = deep_patch is " +
                             "currently available. For a custom usage " +
                             "(advanced users), modify this routine.")

    def run_one_scan(self, scan_file, scan_number, silent=True):
        """
        Generate one observation (i.e. one CES) of the telescope.

        Parameters
        ----------
        scan_file : dictionary
            Empty dictionary which will contain the outputs of the scan.
        scan_number : int
            Index of the scan (between 0 and nces - 1).
        silent : bool
            If False, print out messages about the scan. Default is True.

        Returns
        ----------
        bool : bool
            Returns True if the scan has been generated, and False if the scan
            already exists on the disk.
        """
        ## Figure out the elevation to run the scan!
        el = self.elevation[scan_number]

        ## Define the sampling rate in Hz
        sampling_freq = self.sampling_freq

        ## Define geometry of the scan by figuring out the azimuth bounds
        az_mean = (self.az_min[scan_number] + self.az_max[scan_number]) * 0.5
        az_throw = (self.az_max[scan_number] -
                    self.az_min[scan_number]) / np.cos(el / radToDeg)

        ## Define the timing bounds!
        LST_now = float(self.telescope_location.sidereal_time()) / (2 * np.pi)
        begin_LST = float(
            ephem.hours(self.begin_LST[scan_number])) / (2 * np.pi)
        end_LST = float(ephem.hours(self.end_LST[scan_number])) / (2 * np.pi)
        if (begin_LST > end_LST):
            begin_LST -= 1.

        ## Reset the date to correspond to the sidereal time to start
        self.telescope_location.date -= (
            (LST_now - begin_LST) * sidDayToSec) * ephem.second

        ## Figure out how long to run the scan for
        num_pts = int((end_LST - begin_LST) * sidDayToSec * sampling_freq)

        ## Run the scan!
        pb_az_dir = 1.
        upper_az = az_mean + az_throw / 2.
        lower_az = az_mean - az_throw / 2.
        az_speed = self.sky_speed / np.cos(el / radToDeg)
        running_az = az_mean

        ## Initialize arrays
        pb_az_array = np.zeros(num_pts)
        pb_mjd_array = np.zeros(num_pts)
        pb_ra_array = np.zeros(num_pts)
        pb_dec_array = np.zeros(num_pts)
        pb_el_array = np.ones(num_pts) * el

        ## Loop over time samples
        begin_lst = str(self.telescope_location.sidereal_time())
        # Pad scans 10 seconds on either side
        time_padding = 10.0 / 86400.0

        ## Start of the scan
        pb_az_array[0] = running_az
        pb_mjd_array[0] = date_to_mjd(self.telescope_location.date)

        ## Initialize the time
        scan_file['firstmjd'] = pb_mjd_array[0] - time_padding

        ## Update before starting the loop
        running_az += az_speed * pb_az_dir / sampling_freq
        self.telescope_location.date += ephem.second / sampling_freq

        if self.language == 'python':
            for t in range(1, num_pts):
                ## Set the Azimuth and time
                pb_az_array[t] = running_az

                pb_ra_array[t], pb_dec_array[t] = \
                    self.telescope_location.radec_of(
                    pb_az_array[t] * np.pi / 180.,
                    pb_el_array[t] * np.pi / 180.)

                ## Case to change the direction of the scan
                if(running_az > upper_az):
                    pb_az_dir = -1.
                elif(running_az < lower_az):
                    pb_az_dir = 1.

                running_az += az_speed * pb_az_dir / sampling_freq

                ## Increment the time by one second / sampling rate
                pb_mjd_array[t] = pb_mjd_array[t-1] + \
                    ephem.second / sampling_freq

                ## Increment the time by one second / sampling rate
                self.telescope_location.date += ephem.second / sampling_freq

        elif self.language == 'C':
            c_code = r'''
            int t;
            for (t=1;t<num_pts;t++)
            {
                // Set the Azimuth and time
                pb_az_array[t] = running_az;

                // Case to change the direction of the scan
                if (running_az > upper_az)
                {
                    pb_az_dir = -1.0;
                }
                else if (running_az < lower_az)
                {
                    pb_az_dir = 1.0;
                }

                running_az += az_speed * pb_az_dir / sampling_freq;

                // Increment the time by one second / sampling rate
                pb_mjd_array[t] = pb_mjd_array[t-1] + second / sampling_freq;
            }
            '''
            second = 1./24./3600.
            az_speed = float(az_speed)
            pb_az_dir = float(pb_az_dir)
            sampling_freq = float(sampling_freq)
            running_az = float(running_az)
            upper_az = float(upper_az)
            lower_az = float(lower_az)
            weave.inline(c_code, [
                'num_pts',
                'running_az', 'pb_az_array', 'upper_az',
                'lower_az', 'az_speed', 'pb_az_dir', 'pb_mjd_array',
                'second', 'sampling_freq'], verbose=0)

        elif self.language == 'fortran':
            second = 1./24./3600.
            scanning_strategy_f.run_one_scan_f(
                pb_az_array, pb_mjd_array,
                running_az, upper_az, lower_az, az_speed, pb_az_dir,
                second, sampling_freq, num_pts)

        ## Do not use that for precision - it truncates values
        self.telescope_location.date += num_pts * ephem.second / sampling_freq

        ## Save in file
        scan_file['nces'] = self.nces
        scan_file['CES'] = scan_number
        scan_file['sample_rate'] = sampling_freq
        scan_file['sky_speed'] = self.sky_speed
        scan_file['lastmjd'] = pb_mjd_array[-1] + time_padding

        scan_file['azimuth'] = pb_az_array * np.pi / 180
        scan_file['elevation'] = pb_el_array * np.pi / 180
        scan_file['clock-utc'] = pb_mjd_array

        scan_file['RA'] = pb_ra_array
        scan_file['Dec'] = pb_dec_array

        scan_file['nts'] = len(pb_mjd_array)

        if not silent:
            print('+-----------------------------------+')
            print(' CES starts at %s and finishes at %s' % (
                mjd_to_greg(scan_file['firstmjd']),
                mjd_to_greg(scan_file['lastmjd'])))
            print(' It lasts %.3f hours' % (
                (scan_file['lastmjd'] - scan_file['firstmjd']) * 24))
            print('+-----------------------------------+')

        ## Add one day before the next CES (to avoid conflict of time)
        self.telescope_location.date += 24 * ephem.second * 3600

        ## Add the scan into the instance
        # self._update('scan{}'.format(scan_number), scan_file)

        return True

    def run(self, silent=True):
        """
        Generate all the observations (i.e. all CES) of the telescope.

        Parameters
        ----------
        silent : bool
            If False, print out messages about the scan. Default is True.

        Examples
        ----------
        >>> scan = ScanningStrategy(sampling_freq=1., nces=2)
        >>> scan.run()
        >>> print(scan.scan0['firstmjd'], scan.scan0['lastmjd'])
        56293.6202546 56293.8230093

        By default, the language used for the core computation is the Python.
        It can be quite slow for heavy configuration, and one can set up
        the language to C or fortran for speeding up the computation (x1000).
        Note that C codes are compiled on-the-fly (weave), but for fortran
        codes you need first to compile it. See the setup.py or
        the provided Makefile.
        >>> scan = ScanningStrategy(sampling_freq=1., nces=2,
        ...     language='fortran')
        >>> scan.run()
        >>> print(scan.scan0['firstmjd'], scan.scan0['lastmjd'])
        56293.6202546 56293.8230093
        """
        ## Initialise the date and loop over CESes
        self.telescope_location.date = self.start_date
        for CES_position in range(self.nces):
            ## Initialise the starting date of observation
            ## It will be updated then automatically
            setattr(self, 'scan{}'.format(CES_position), {})

            # Create the scan strategy
            self.run_one_scan(
                getattr(self, 'scan{}'.format(CES_position)),
                CES_position, silent=silent)

    def visualize_my_scan(self, nside, reso=6.9, xsize=900, rot=[0, -57.5],
                          nfid_bolometer=6000, fp_size=180., boost=1.,
                          test=False):
        """
        Simple map-making: project time ordered data into sky maps for
        visualisation. It works only in pure python (i.e. if you set
        language='python' when initialising the scanning_strategy class).

        Parameters
        ----------
        nside : int
            Resolution of the healpix map.
        reso : float
            Resolution of the projected map (pixel size) in arcmin.
        xsize : int
            Number of pixel per row for the projected map.
        rot : 1d array of float
            Coordinates of the center of
            the projected map [lon, lat] in degree
        nfid_bolometer : int
            Fiducial number of bolometers for visualisation.
            By default, the scans are done for one reference bolometer.
        fp_size : float
            Size of the focal plane on the sky, in arcmin.
        boost : int
            boost factor to artificially increase the number of hits.
            It doesn't change the shape of the survey (just the amplitude).
        test : bool
            If True, doesn't display the result (mainly for test mode).

        Outputs
        ----------
            * nhit_loc: 1D array, sky map with cumulative hit counts

        """
        if self.language != 'python':
            raise ValueError("Visualisation is available only in pure " +
                             "python because we do not provide (yet) " +
                             "RA and Dec in C or fortran. Relaunch " +
                             "using language='python' in the class " +
                             "ScanningStrategy.")

        npix = hp.pixelfunc.nside2npix(nside)
        nhit = np.zeros(npix)
        for scan_number in range(self.nces):
            scan = getattr(self, 'scan{}'.format(scan_number))

            num_pts = len(scan['clock-utc'])
            pix_global = hp.pixelfunc.ang2pix(
                nside, (np.pi/2.) - scan['Dec'], scan['RA'])

            ## Boresight pointing healpix maps
            nhit_loc = np.zeros(npix)

            ## language = C or language = fortran are not yet supported
            ## because they are not returning RA and Dec. So for the moment
            ## only language == python is considered.
            ## TODO Compute RA and Dec in C and Fortran.
            if self.language in ['python', 'C']:
                c_code = r"""
                int i, pix;
                double c, s;
                for (i=0;i<num_pts;i++)
                {
                    pix = pix_global[i];

                    // Number of hits per pixel
                    nhit_loc[pix] += 1;
                }
                """

                weave.inline(c_code, [
                    'pix_global',
                    'num_pts',
                    'nhit_loc'], verbose=0)
            elif self.language == 'fortran':
                scanning_strategy_f.mapmaking(
                    pix_global, nhit_loc, npix, num_pts)

            ## Fake large focal plane with many bolometers for visualisation.
            nhit_loc = convolve_focalplane(nhit_loc, nfid_bolometer,
                                           fp_size, boost,
                                           language=self.language)

            nhit += nhit_loc

        ## Display the result of not testing.
        if test:
            import matplotlib
            matplotlib.use("Agg")
        import pylab as pl

        print('Stats: nhits = {}/{} (fsky={}%), max hit = {}'.format(
            len(nhit[nhit > 0]),
            len(nhit),
            round(len(nhit[nhit > 0])/len(nhit) * 100, 2),
            int(np.max(nhit))))
        nhit[nhit == 0] = hp.UNSEEN
        hp.gnomview(nhit, rot=rot, reso=reso, xsize=xsize,
                    cmap=pl.cm.viridis,
                    title='nbolos = {}, '.format(nfid_bolometer) +
                    'fp size = {} arcmin, '.format(fp_size) +
                    'nhit boost = {}'.format(boost))
        if not test:
            hp.graticule()

        pl.show()
        pl.clf()

    def _update(self, name, value):
        """
        Wrapper around setattr function.
        Set a named attribute on an object.

        Parameters
        ----------
        name : string
            The name of the new attribute
        value : *
            The value of the attribute.
        """
        setattr(self, name, value)

def convolve_focalplane(bore_nhits, nbolos,
                        fp_radius_amin, boost, language='C'):
    """
    Given a nHits and bore_cos and bore_sin map,
    perform the focal plane convolution.
    Original author: Neil Goeckner-Wald.
    Modifications by Julien Peloton.

    Parameters
    ----------
    bore_nhits : 1D array
        number of hits for the reference detector.
    bore_cos : 1D array
        cumulative cos**2 for the reference detector.
    bore_sin : 1D array
        cumulative sin**2 for the reference detector.
    bore_cs : 1D array
        cumulative cos*sin for the reference detector.
    nbolos : int
        total number of bolometers desired.
    fp_radius_amin : float
        radius of the focal plane in arcmin.
    boost : float
        boost factor to artificially increase the number of hits.
        It doesn't change the shape of the survey (just the amplitude).
    language : string, optional
        Language to use to perform core computation: C or fortran.
        Default is C (compiled on-the-fly via weave). To use fortran,
        you need to compile the source (see the Makefile provided).

    Returns
    ----------
    focalplane_nhits : 1D array
        Number of hits for the all the detectors.

    """
    # Now we want to make the focalplane maps
    focalplane_nhits = np.zeros(bore_nhits.shape)

    # Resolution of our healpix map
    nside = hp.npix2nside(focalplane_nhits.shape[0])
    resol_amin = hp.nside2resol(nside, arcmin=True)
    fp_rad_bins = int(fp_radius_amin * 2. / resol_amin)
    fp_diam_bins = (fp_rad_bins * 2) + 1

    # Build the focal plane model and a list of offsets
    (x_fp, y_fp) = np.array(
        np.unravel_index(
            range(0, fp_diam_bins**2),
            (fp_diam_bins, fp_diam_bins))).reshape(
                2, fp_diam_bins, fp_diam_bins) - (fp_rad_bins)
    fp_map = ((x_fp**2 + y_fp**2) < (fp_rad_bins)**2)

    bolo_per_pix = nbolos / float(np.sum(fp_map))

    dRA = np.ndarray.flatten(
        (x_fp[fp_map].astype(float) * fp_radius_amin) / (
            fp_rad_bins * 60. * (180. / (np.pi))))
    dDec = np.ndarray.flatten(
        (y_fp[fp_map].astype(float) * fp_radius_amin) / (
            fp_rad_bins * 60. * (180. / (np.pi))))

    pixels_global = np.array(np.where(bore_nhits != 0)[0], dtype=int)
    for n in pixels_global:
        n = int(n)

        # Compute pointing offsets
        (theta_bore, phi_bore) = hp.pix2ang(nside, n)
        phi = phi_bore + dRA * np.sin(theta_bore)
        theta = theta_bore + dDec

        pixels = hp.ang2pix(nside, theta, phi)
        npix_loc = len(pixels)

        ## Necessary because the values in pixels aren't necessarily unique
        ## This is a poor design choice and should probably be fixed

        ## language = C or language = fortran are not yet supported
        ## because they are not returning RA and Dec. So for the moment
        ## only language == python is considered.
        ## TODO Compute RA and Dec in C and Fortran.
        if language in ['python', 'C']:
            c_code = r"""
            int i, pix;
            for (i=0;i<npix_loc;i++)
            {
                pix = pixels[i];
                focalplane_nhits[pix] += bore_nhits[n] * \
                bolo_per_pix * boost;
            }
            """

            weave.inline(c_code, [
                'bore_nhits',
                'focalplane_nhits',
                'pixels', 'bolo_per_pix',
                'npix_loc', 'n', 'boost'], verbose=0)

        elif language == 'fortran':
            scanning_strategy_f.convolve_focalplane_f(
                bore_nhits, focalplane_nhits, pixels,
                bolo_per_pix, boost, npix_loc)

    return focalplane_nhits

## Here are a bunch of routines to handle dates...

def date_to_mjd(date):
    """
    Convert date in ephem.date format to MJD.

    Parameters
    ----------
    date : ephem.Date
        Floating point value used by ephem to represent a date.
        The value is the number of days since 1899 December 31 12:00 UT. When
        creating an instance you can pass in a Python datetime instance,
        timetuple, year-month-day triple, or a plain float.
        Run str() on this object to see the UTC date it represents.
        ...
        WTF?

    Returns
    ----------
    mjd : float
        Date in the format MJD.

    Examples
    ----------
    >>> e = ephem.Observer()
    >>> e.date = 0.0 ## 1899 December 31 12:00 UT
    >>> mjd = date_to_mjd(e.date)
    >>> print('DATE={} ->'.format(round(e.date, 2)),
    ...     'MJD={}'.format(round(mjd, 2)))
    DATE=0.0 -> MJD=15019.5
    """
    return greg_to_mjd(date_to_greg(date))

def date_to_greg(date):
    """
    Convert date in ephem.date format to gregorian date.

    Parameters
    ----------
    date : ephem.Date
        Floating point value used by ephem to represent a date.
        The value is the number of days since 1899 December 31 12:00 UT. When
        creating an instance you can pass in a Python datetime instance,
        timetuple, year-month-day triple, or a plain float.
        Run str() on this object to see the UTC date it represents.
        ...
        WTF?

    Returns
    ----------
    greg : string
        Gregorian date (format: YYYYMMDD_HHMMSS)

    Examples
    ----------
    >>> e = ephem.Observer()
    >>> e.date = 0.0 ## 1899 December 31 12:00 UT
    >>> greg = date_to_greg(e.date)
    >>> print('DATE={} ->'.format(round(e.date, 2)),
    ...     'GREG={}'.format(greg))
    DATE=0.0 -> GREG=18991231_120000
    """
    date_ = str(date)
    date_ = str(date.datetime())
    greg = date_.split('.')[0].replace('-',
                                       '').replace(':',
                                                   '').replace(' ',
                                                               '_')

    return greg

def greg_to_mjd(greg):
    """
    Convert gregorian date into MJD.

    Parameters
    ----------
    greg : string
        Gregorian date (format: YYYYMMDD_HHMMSS)

    Returns
    ----------
    mjd : float
        Date in the format MJD.

    Examples
    ----------
    >>> greg = '19881103_000000'
    >>> mjd = greg_to_mjd(greg)
    >>> print('GREG={} ->'.format(greg), 'MJD={}'.format(round(mjd, 2)))
    GREG=19881103_000000 -> MJD=47468.0
    """
    year = int(greg[:4])
    month = int(greg[4:6])
    day = int(greg[6:8])
    hour = int(greg[9:11])
    minute = int(greg[11:13])
    second = int(greg[13:15])

    fracday, status = slalib.sla_dtf2d(hour, minute, second)
    mjd, status = slalib.sla_cldj(year, month, day)
    mjd += fracday

    return mjd

def mjd_to_greg(mjd):
    """
    Convert MJD into gregorian date.

    Parameters
    ----------
    mjd : float
        Date in the format MJD.

    Returns
    ----------
    greg : string
        Gregorian date (format: YYYYMMDD_HHMMSS)

    Examples
    ----------
    >>> mjd = greg_to_mjd('19881103_000000')
    >>> greg = mjd_to_greg(mjd)
    >>> print('MJD={} ->'.format(round(mjd, 2)), 'GREG={}'.format(greg))
    MJD=47468.0 -> GREG=19881103_000000
    """
    year, month, day, fracday, baddate = slalib.sla_djcl(mjd)

    if baddate:
        raise ValueError(BadMJD)

    sign, (hour, minute, second, frac) = slalib.sla_dd2tf(2, fracday)

    s = '{:4d}{:2d}{:2d}_{:2d}{:2d}{:2d}'.format(
        year, month, day, hour, minute, second)
    s = s.replace(' ', '0')

    return s


if __name__ == "__main__":
    import doctest
    doctest.testmod()
