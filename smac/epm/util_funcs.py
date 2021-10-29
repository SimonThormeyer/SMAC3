import typing
import logging
import numpy as np

from ConfigSpace import ConfigurationSpace
from ConfigSpace.hyperparameters import CategoricalHyperparameter, \
    UniformFloatHyperparameter, UniformIntegerHyperparameter, Constant, \
    OrdinalHyperparameter
from smac.utils.constants import MAXINT

__copyright__ = "Copyright 2021, AutoML.org Freiburg-Hannover"
__license__ = "3-clause BSD"


def get_types(
        config_space: ConfigurationSpace,
        instance_features: typing.Optional[np.ndarray] = None,
) -> typing.Tuple[typing.List[int], typing.List[typing.Tuple[float, float]]]:
    """TODO"""
    # Extract types vector for rf from config space and the bounds
    types = [0] * len(config_space.get_hyperparameters())
    bounds = [(np.nan, np.nan)] * len(types)

    for i, param in enumerate(config_space.get_hyperparameters()):
        parents = config_space.get_parents_of(param.name)
        if len(parents) == 0:
            can_be_inactive = False
        else:
            can_be_inactive = True

        if isinstance(param, (CategoricalHyperparameter)):
            n_cats = len(param.choices)
            if can_be_inactive:
                n_cats = len(param.choices) + 1
            types[i] = n_cats
            bounds[i] = (int(n_cats), np.nan)

        elif isinstance(param, (OrdinalHyperparameter)):
            n_cats = len(param.sequence)
            types[i] = 0
            if can_be_inactive:
                bounds[i] = (0, int(n_cats))
            else:
                bounds[i] = (0, int(n_cats) - 1)

        elif isinstance(param, Constant):
            # for constants we simply set types to 0 which makes it a numerical
            # parameter
            if can_be_inactive:
                bounds[i] = (2, np.nan)
                types[i] = 2
            else:
                bounds[i] = (0, np.nan)
                types[i] = 0
            # and we leave the bounds to be 0 for now
        elif isinstance(param, UniformFloatHyperparameter):
            # Are sampled on the unit hypercube thus the bounds
            # are always 0.0, 1.0
            if can_be_inactive:
                bounds[i] = (-1.0, 1.0)
            else:
                bounds[i] = (0, 1.0)
        elif isinstance(param, UniformIntegerHyperparameter):
            if can_be_inactive:
                bounds[i] = (-1.0, 1.0)
            else:
                bounds[i] = (0, 1.0)
        elif not isinstance(param, (UniformFloatHyperparameter,
                                    UniformIntegerHyperparameter,
                                    OrdinalHyperparameter,
                                    CategoricalHyperparameter)):
            raise TypeError("Unknown hyperparameter type %s" % type(param))

    if instance_features is not None:
        types = types + [0] * instance_features.shape[1]

    return types, bounds


def get_rng(
        rng: typing.Optional[typing.Union[int, np.random.RandomState]] = None,
        run_id: typing.Optional[int] = None,
        logger: typing.Optional[logging.Logger] = None,
) -> typing.Tuple[int, np.random.RandomState]:
    """
    Initialize random number generator and set run_id

    * If rng and run_id are None, initialize a new generator and sample a run_id
    * If rng is None and a run_id is given, use the run_id to initialize the rng
    * If rng is an int, a RandomState object is created from that.
    * If rng is RandomState, return it
    * If only run_id is None, a run_id is sampled from the random state.

    Parameters
    ----------
    rng : np.random.RandomState|int|None
    run_id : int, optional
    logger: logging.Logger, optional

    Returns
    -------
    int
    np.random.RandomState

    """
    if logger is None:
        logger = logging.getLogger('GetRNG')
    # initialize random number generator
    if rng is not None and not isinstance(rng, (int, np.random.RandomState)):
        raise TypeError('Argument rng accepts only arguments of type None, int or np.random.RandomState, '
                        'you provided %s.' % str(type(rng)))
    if run_id is not None and not isinstance(run_id, int):
        raise TypeError('Argument run_id accepts only arguments of type None, int, '
                        'you provided %s.' % str(type(run_id)))

    if rng is None and run_id is None:
        # Case that both are None
        logger.debug('No rng and no run_id given: using a random value to initialize run_id.')
        rng_return = np.random.RandomState()
        run_id_return = rng_return.randint(MAXINT)
    elif rng is None and isinstance(run_id, int):
        logger.debug('No rng and no run_id given: using run_id %d as seed.', run_id)
        rng_return = np.random.RandomState(seed=run_id)
        run_id_return = run_id
    elif isinstance(rng, int) and run_id is None:
        run_id_return = rng
        rng_return = np.random.RandomState(seed=rng)
    elif isinstance(rng, int) and isinstance(run_id, int):
        run_id_return = run_id
        rng_return = np.random.RandomState(seed=rng)
    elif isinstance(rng, np.random.RandomState) and run_id is None:
        rng_return = rng
        run_id_return = rng.randint(MAXINT)
    elif isinstance(rng, np.random.RandomState) and isinstance(run_id, int):
        rng_return = rng
        run_id_return = run_id
    else:
        raise ValueError('This should not happen! Please contact the developers! Arguments: rng=%s of type %s and '
                         'run_id=%s of type %s' % (rng, type(rng), str(run_id), type(run_id)))
    return run_id_return, rng_return


def check_points_in_ss(X: np.ndarray,
                       cont_dims: np.ndarray,
                       cat_dims: np.ndarray,
                       bounds_cont: np.ndarray,
                       bounds_cat: typing.List[typing.List[typing.Tuple]],
                       expand_bound: bool = False,
                       ):
    """
    check which points will be place inside a subspace
    Parameters
    ----------
    X: np.ndarray(N,D),
        points to be checked, where D = D_cont + D_cat
    cont_dims: np.ndarray(D_cont)
        which dimensions represent continuous hyperparameters
    cat_dims: np.ndarray(D_cat)
        which dimensions represent categorical hyperparameters
    bounds_cont: typing.List[typing.Tuple]
        subspaces bounds of categorical hyperparameters, its length is the number of categorical hyperparameters
    bounds_cat: np.ndarray(D_cont, 2)
        subspaces bounds of continuous hyperparameters, its length is the number of categorical hyperparameters
    expand_bound: bool
        if the bound needs to be expanded to contain more points rather than the points inside the subregion
    Return
    ----------
    indices_in_ss:np.ndarray(N)
        indices of data that included in subspaces
    """
    if len(X.shape) == 1:
        X = X[np.newaxis, :]

    if cont_dims.size != 0:
        data_in_ss = np.all(X[:, cont_dims] <= bounds_cont[:, 1], axis=1) & np.all(X[:, cont_dims] >= bounds_cont[:, 0],
                                                                                   axis=1)

        if expand_bound:
            bound_left = bounds_cont[:, 0] - np.min(X[data_in_ss][:, cont_dims] - bounds_cont[:, 0], axis=0)
            bound_right = bounds_cont[:, 1] + np.min(bounds_cont[:, 1] - X[data_in_ss][:, cont_dims], axis=0)
            data_in_ss = np.all(X[:, cont_dims] <= bound_right, axis=1) & np.all(X[:, cont_dims] >= bound_left, axis=1)
    else:
        data_in_ss = np.ones(X.shape[-1], dtype=bool)

    # TODO find out where cause the None value of  bounds_cat
    if bounds_cat is None:
        bounds_cat = [()]

    for bound_cat, cat_dim in zip(bounds_cat, cat_dims):
        data_in_ss &= np.in1d(X[:, cat_dim], bound_cat)

    return data_in_ss
