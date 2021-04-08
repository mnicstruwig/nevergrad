# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import numpy as np
import os
from . import gym_multi


def test_gym_multi() -> None:
    for env_name in gym_multi.GymMulti.ng_gym:
        assert env_name in gym_multi.GymMulti.env_names, f"{env_name} unknown!"
        assert env_name not in gym_multi.NO_LENGTH, f"{env_name} in no length and in ng_gym!"
    for env_name in gym_multi.GUARANTEED_GYM_ENV_NAMES:
        assert env_name in gym_multi.GymMulti.env_names, f"{env_name} should be guaranteed!"
    assert len(gym_multi.GYM_ENV_NAMES) == 26


def test_run_gym_multi() -> None:
    if os.name != "nt":
        func = gym_multi.GymMulti(randomized=False)
        x = np.zeros(func.dimension)
        value = func(x)
        np.testing.assert_almost_equal(value, 93.35, decimal=2)
        for i, name in enumerate(gym_multi.GYM_ENV_NAMES):
            control = gym_multi.CONTROLLERS[i % len(gym_multi.CONTROLLERS)]
            func = gym_multi.GymMulti(
                name,
                control,
                randomized=bool(np.random.randint(2)),
            )
            # x = np.zeros(func.dimension)
            x = func.parametrization.sample()
            value = func(x.value)