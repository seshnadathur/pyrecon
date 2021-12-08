import os
import sys
import subprocess

import numpy as np
import fitsio

from pyrecon import PlaneParallelFFTReconstruction
from test_multigrid import get_random_catalog


def test_dtype():
    data = get_random_catalog(seed=42)
    randoms = get_random_catalog(seed=81)
    for los in ['x']:
        recon_f4 = PlaneParallelFFTReconstruction(f=0.8,bias=2.,nthreads=4,positions=randoms['Position'],nmesh=64,los=los,dtype='f4')
        recon_f4.assign_data(data['Position'],data['Weight'])
        recon_f4.assign_randoms(randoms['Position'],randoms['Weight'])
        recon_f4.set_density_contrast()
        assert recon_f4.mesh_delta.dtype.itemsize == 4
        recon_f4.run()
        assert recon_f4.mesh_psi[0].dtype.itemsize == 4
        shifts_f4 = recon_f4.read_shifts(data['Position'].astype('f8'),field='disp+rsd')
        assert shifts_f4.dtype.itemsize == 8
        shifts_f4 = recon_f4.read_shifts(data['Position'].astype('f4'),field='disp+rsd')
        assert shifts_f4.dtype.itemsize == 4
        recon_f8 = PlaneParallelFFTReconstruction(f=0.8,bias=2.,nthreads=4,positions=randoms['Position'],nmesh=64,los=los,dtype='f8')
        recon_f8.assign_data(data['Position'],data['Weight'])
        recon_f8.assign_randoms(randoms['Position'],randoms['Weight'])
        recon_f8.set_density_contrast()
        assert recon_f8.mesh_delta.dtype.itemsize == 8
        recon_f8.run()
        assert recon_f8.mesh_psi[0].dtype.itemsize == 8
        shifts_f8 = recon_f8.read_shifts(data['Position'],field='disp+rsd')
        assert shifts_f8.dtype.itemsize == 8
        assert not np.all(shifts_f4 == shifts_f8)
        assert np.allclose(shifts_f4, shifts_f8, atol=1e-2, rtol=1e-2)


def test_mem():
    data = get_random_catalog(seed=42)
    randoms = get_random_catalog(seed=84)
    from pyrecon.utils import MemoryMonitor
    with MemoryMonitor() as mem:
        recon = PlaneParallelFFTReconstruction(f=0.8,bias=2.,nthreads=4,positions=randoms['Position'],nmesh=256,los='x',dtype='f8')
        mem('init')
        recon.assign_data(data['Position'],data['Weight'])
        mem('data')
        recon.assign_randoms(randoms['Position'],randoms['Weight'])
        mem('randoms')
        recon.set_density_contrast()
        mem('delta')
        recon.run()
        mem('recon') # 3 meshes


def test_plane_parallel_fft(data_fn, randoms_fn):
    boxsize = 1200.
    boxcenter = [1754, 400, 400]
    data = fitsio.read(data_fn)
    randoms = fitsio.read(randoms_fn)
    data = {name: data[name] for name in data.dtype.names}
    randoms = {name: randoms[name] for name in randoms.dtype.names}
    recon = PlaneParallelFFTReconstruction(f=0.8,bias=2.,los='x',nthreads=4,boxcenter=boxcenter,boxsize=boxsize,nmesh=128,dtype='f8')
    recon.assign_data(data['Position'],data['Weight'])
    recon.assign_randoms(randoms['Position'],randoms['Weight'])
    recon.set_density_contrast()
    recon.run()

    data['Position_rec'] = data['Position'] - recon.read_shifts(data['Position'])
    randoms['Position_rec'] = randoms['Position'] - recon.read_shifts(randoms['Position'], field='disp')

    from matplotlib import pyplot as plt
    from nbodykit.lab import ArrayCatalog, FKPCatalog, ConvolvedFFTPower
    data = ArrayCatalog(data)
    randoms = ArrayCatalog(randoms)

    for catalog in [data,randoms]:
        catalog['WEIGHT_FKP'] = np.ones(catalog.size,dtype='f8')
        catalog['WEIGHT_COMP'] = catalog['Weight']

    fkp = FKPCatalog(data, randoms)
    BoxSize = 1000.
    Nmesh = 128
    ells = (0, 2)
    mesh = fkp.to_mesh(position='Position',fkp_weight='WEIGHT_FKP',comp_weight='WEIGHT_COMP',nbar='NZ',BoxSize=BoxSize,Nmesh=Nmesh,resampler='tsc',interlaced=True,compensated=True)
    power = ConvolvedFFTPower(mesh,poles=ells,kmin=0.,dk=0.01)

    mesh = fkp.to_mesh(position='Position_rec',fkp_weight='WEIGHT_FKP',comp_weight='WEIGHT_COMP',nbar='NZ',BoxSize=BoxSize,Nmesh=Nmesh,resampler='tsc',interlaced=True,compensated=True)
    power_rec = ConvolvedFFTPower(mesh,poles=ells,kmin=0.,dk=0.01)

    for ill,ell in enumerate(ells):
        pk = power.poles['power_{:d}'.format(ell)] - power.attrs['shotnoise'] if ell == 0 else power.poles['power_{:d}'.format(ell)]
        plt.plot(power.poles['k'],power.poles['k']*pk,color='C{:d}'.format(ill),linestyle='-')
        pk = power_rec.poles['power_{:d}'.format(ell)] - power_rec.attrs['shotnoise'] if ell == 0 else power_rec.poles['power_{:d}'.format(ell)]
        plt.plot(power_rec.poles['k'],power_rec.poles['k']*pk,color='C{:d}'.format(ill),linestyle='--')

    plt.show()


if __name__ == '__main__':

    import utils
    from utils import data_fn, randoms_fn
    from pyrecon.utils import setup_logging

    setup_logging()
    #test_mem()
    test_dtype()
    test_plane_parallel_fft(data_fn, randoms_fn)
