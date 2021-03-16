# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import numpy as np
from . import gym_anm


def test_gym_anm() -> None:
    func = gym_anm.GymAnm()
    x = 0 * np.random.rand(func.dimension)
    value = func(x)  # should not touch boundaries, so value should be < np.inf
    np.testing.assert_almost_equal(value, 0.0)