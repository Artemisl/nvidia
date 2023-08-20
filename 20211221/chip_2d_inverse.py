from sympy import Symbol
import numpy as np
import tensorflow as tf
import sys
sys.path.append('../../SimNet/')

from simnet.solver import Solver
from simnet.dataset import TrainDomain, ValidationDomain, MonitorDomain
from simnet.data import Validation, Monitor, BC
from simnet.sympy_utils.geometry_2d import Rectangle, Line, Channel2D
from simnet.sympy_utils.functions import parabola
from simnet.csv_utils.csv_rw import csv_to_dict
from simnet.PDES.navier_stokes import IntegralContinuity, NavierStokes
from simnet.controller import SimNetController
from simnet.architecture import FourierNetArch

# define sympy variables to parametrize domain curves
x, y = Symbol('x'), Symbol('y')

# validation data
mapping = {'Points:0': 'x', 'Points:1': 'y',
           'U:0': 'u', 'U:1': 'v', 'p': 'p'}
openfoam_var = csv_to_dict('openfoam/2D_chip_fluid0.csv', mapping)
openfoam_var['x'] -= 2.5 # normalize pos
openfoam_var['y'] -= 0.5
openfoam_invar_numpy = {key: value for key, value in openfoam_var.items() if key in ['x', 'y']}
openfoam_outvar_numpy = {key: value for key, value in openfoam_var.items() if key in ['u', 'v', 'p']}
openfoam_outvar_numpy['continuity'] = np.zeros_like(openfoam_outvar_numpy['u'])
openfoam_outvar_numpy['momentum_x'] = np.zeros_like(openfoam_outvar_numpy['u'])
openfoam_outvar_numpy['momentum_y'] = np.zeros_like(openfoam_outvar_numpy['u'])

class Chip2DTrain(TrainDomain):
  def __init__(self, **config):
    super(Chip2DTrain, self).__init__()
    
    interior=BC.from_numpy(openfoam_invar_numpy,openfoam_outvar_numpy,batch_size=1024)
    self.add(interior, name="Interior")


class Chip2DMonitor(MonitorDomain):
  def __init__(self, **config):
    super(Chip2DMonitor, self).__init__()
    
    global_monitor = Monitor(openfoam_invar_numpy, {'average_nu': lambda var: tf.reduce_mean(var['nu'])})
    self.add(global_monitor, 'GlobalMonitor')


class ChipSolver(Solver):
  train_domain = Chip2DTrain
  monitor_domain = Chip2DMonitor

  def __init__(self, **config):
    super(ChipSolver, self).__init__(**config)

    self.equations = (NavierStokes(nu='nu', rho=1, dim=2, time=False).make_node(stop_gradients=['u', 'u__x', 'u__x__x', 'u__y', 'u__y__y',
                                                                                                'v', 'v__x', 'v__x__x', 'v__y', 'v__y__y',
                                                                                                'p', 'p__x', 'p__y']))

    flow_net = self.arch.make_node(name='flow_net',
                                   inputs=['x', 'y'],
                                   outputs=['u', 'v', 'p'])
    invert_net = self.arch.make_node(name='invert_net',
                                     inputs=['x', 'y'],
                                     outputs=['nu'])
    self.nets = [flow_net, invert_net]

  @classmethod
  def update_defaults(cls, defaults):
    defaults.update({
        'network_dir': './network_checkpoint_chip_2d_inverse',
        'rec_results': True,
        'rec_results_freq': 100,
        'start_lr': 3e-4,
        'max_steps': 40000,
        'decay_steps': 100,
        'xla': True
        })
if __name__ == '__main__':
  ctr = SimNetController(ChipSolver)
  ctr.run()
