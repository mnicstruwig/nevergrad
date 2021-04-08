# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import numpy as np
import os
import gym
import nevergrad as ng

if os.name != "nt":
    import gym_anm  # pylint: disable=unused-import
from nevergrad.parametrization import parameter
from ..base import ExperimentFunction


## Method for building a new list, for a future version of gym:

GYM_ENV_NAMES = []

for e in gym.envs.registry.all():
    try:
        assert "Kelly" not in str(e.id)
        env = gym.make(e.id)
        a1 = np.asarray(env.action_space.sample())
        a2 = np.asarray(env.action_space.sample())
        a3 = np.asarray(env.action_space.sample())
        a1 = a1 + a2 + a3
        if hasattr(a1, "size"):
            try:
                assert a1.size < 15000
            except:
                assert a1.size() < 15000
        GYM_ENV_NAMES.append(e.id)
        # print(f"adding {e.id}, {len(GYM_ENV_NAMES)} environments...")
    except:
        pass

GUARANTEED_GYM_ENV_NAMES = [
    "Copy-v0",
    "RepeatCopy-v0",
    "ReversedAddition-v0",
    "ReversedAddition3-v0",
    "DuplicatedInput-v0",
    "Reverse-v0",
    "CartPole-v0",
    "CartPole-v1",
    "MountainCar-v0",
    "Acrobot-v1",
    "Blackjack-v0",
    "FrozenLake-v0",
    "FrozenLake8x8-v0",
    "CliffWalking-v0",
    "NChain-v0",
    "Roulette-v0",
    "Taxi-v3",
    "CubeCrash-v0",
    "CubeCrashSparse-v0",
    "CubeCrashScreenBecomesBlack-v0",
    "MemorizeDigits-v0",
]


# We do not use "conformant" which is not consistent with the rest.
CONTROLLERS = [
    "linear",
    "neural",
    "deep_neural",
    "semideep_neural",
    "structured_neural",
    "memory_neural",
    "stackingmemory_neural",
    "deep_memory_neural",
    "deep_stackingmemory_neural",
    "semideep_memory_neural",
    "semideep_stackingmemory_neural",
    "multi_neural",
    "noisy_neural",
    "noisy_scrambled_neural",
    "scrambled_neural",
    "stochastic_conformant",
]


NO_LENGTH = ["ANM", "Blackjack", "CliffWalking", "Cube", "Memorize"]


class GymMulti(ExperimentFunction):

    env_names = GYM_ENV_NAMES

    controllers = CONTROLLERS

    ng_gym = [
        "Copy-v0",
        "RepeatCopy-v0",
        "Reverse-v0",
        "CartPole-v0",
        "CartPole-v1",
        "Acrobot-v1",
        "FrozenLake-v0",
        "FrozenLake8x8-v0",
        "NChain-v0",
        "Roulette-v0",
]   


    def __init__(
        self,
        name: str = "gym_anm:ANM6Easy-v0",
        control: str = "conformant",
        neural_factor: int = 2,
        randomized: bool = True,
    ) -> None:
        if os.name == "nt":
            raise ng.errors.UnsupportedExperiment("Windows is not supported")
        env = gym.make(name)
        o = env.reset()
        self.env = env

        # Build various attributes.
        self.name = name + "__" + control + "__" + str(neural_factor)
        if randomized:
            self.name += "_unseeded"
        self.randomized = randomized
        try:
            self.num_time_steps = env._max_episode_steps  # I know! This is a private variable.
        except AttributeError:  # Not all environements have a max number of episodes!
            assert any(x in name for x in NO_LENGTH), name
            self.num_time_steps = 100
        self.neural_factor = neural_factor

        # Infer the action space.
        if isinstance(env.action_space, gym.spaces.Discrete):
            output_dim = env.action_space.n
            output_shape = (output_dim,)
            discrete = True
            assert output_dim is not None, env.action_space.n
        else:  # Continuous action space
            output_shape = env.action_space.shape
            if output_shape is None:
                output_shape = tuple(np.asarray(env.action_space.sample()).shape)  # type: ignore
            # When the shape is not available we might do:
            # output_shape = tuple(np.asarray(env.action_space.sample()).shape)  # type: ignore
            discrete = False
            output_dim = np.prod(output_shape)
        self.discrete = discrete

        # Infer the observation space.
        if env.observation_space.dtype == int:
            # Direct inference for corner cases:
            # if "int" in str(type(o)):
            input_dim = env.observation_space.n
            assert input_dim is not None, env.observation_space.n
            self.discrete_input = True
        else:
            input_dim = np.prod(env.observation_space.shape)
            if input_dim is None:
                input_dim = np.prod(np.asarray(o).shape)
            self.discrete_input = False

        # Infer the action type.
        a = env.action_space.sample()
        self.action_type = type(a)
        self.subaction_type = None
        if hasattr(a, "__iter__"):
            self.subaction_type = type(a[0])

        # Prepare the policy shape.
        self.output_shape = output_shape
        self.num_stacking = 1
        self.memory_len = neural_factor * input_dim if "memory" in control else 0
        self.extended_input_len = (input_dim + output_dim) * self.num_stacking if "stacking" in control else 0
        input_dim = input_dim + self.memory_len + self.extended_input_len
        self.extended_input = np.zeros(self.extended_input_len)
        output_dim = output_dim + self.memory_len
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.num_neurons = neural_factor * (input_dim - self.extended_input_len)
        self.num_internal_layers = 1 if "semi" in control else 3
        internal = self.num_internal_layers * (self.num_neurons**2) if "deep" in control else 0
        unstructured_neural_size = (output_dim * self.num_neurons + self.num_neurons * (input_dim + 1) + internal,)
        neural_size = unstructured_neural_size
        assert control in CONTROLLERS or control == "conformant", f"{control} not known as a form of control"
        self.control = control
        if "neural" in control:
            self.first_size = self.num_neurons * (self.input_dim + 1)
            self.second_size = self.num_neurons * self.output_dim
            self.first_layer_shape = (self.input_dim + 1, self.num_neurons)
            self.second_layer_shape = (self.num_neurons, self.output_dim)
        shape_dict = {
            "conformant": (self.num_time_steps,) + output_shape,
            "stochastic_conformant": (self.num_time_steps,) + output_shape,
            "linear": (input_dim + 1, output_dim),
            "memory_neural": neural_size,
            "stackingmemory_neural": neural_size,
            "neural": neural_size,
            "deep_neural": neural_size,
            "semideep_neural": neural_size,
            "deep_memory_neural": neural_size,
            "semideep_memory_neural": neural_size,
            "deep_stackingmemory_neural": neural_size,
            "semideep_stackingmemory_neural": neural_size,
            "structured_neural": neural_size,
            "multi_neural": (min(self.num_time_steps, 50),) + unstructured_neural_size,
            "noisy_neural": neural_size,
            "noisy_scrambled_neural": neural_size,
            "scrambled_neural": neural_size,
        }
        shape = shape_dict[control]
        assert all(
            c in shape_dict for c in self.controllers
        ), f"{self.controllers} subset of {shape_dict.keys()}"
        shape = tuple(map(int, shape))
        self.policy_shape = shape if "structured" not in control else None

        # Create the parametrization.
        parametrization = parameter.Array(shape=shape).set_name("ng_default")
        if "structured" in control and "neural" in control and "multi" not in control:
            parametrization = parameter.Instrumentation(  # type: ignore
                parameter.Array(shape=tuple(map(int, self.first_layer_shape))),
                parameter.Array(shape=tuple(map(int, self.second_layer_shape))),
            ).set_name("ng_struct")
        if "conformant" in control:
            try:
                if env.action_space.low is not None and env.action_space.high is not None:
                    low = np.repeat(np.expand_dims(env.action_space.low, 0), self.num_time_steps, axis=0)
                    high = np.repeat(np.expand_dims(env.action_space.high, 0), self.num_time_steps, axis=0)
                    init = 0.5 * (low + high)
                    parametrization = parameter.Array(init=init)
                    parametrization.set_bounds(low, high)
            except AttributeError:  # Not all env.action_space have a low and a high.
                pass
            if self.subaction_type == int:
                parametrization.set_integer_casting()
            parametrization.set_name("conformant")

        # Now initializing.
        super().__init__(self.gym_multi_function, parametrization=parametrization)
        self.archive = []

    def evaluation_function(self, *recommendations) -> float:
        x = recommendations[0].value
        if not self.randomized:
            return self.gym_multi_function(x)
        losses = [self.gym_multi_function(x) for _ in range(100)]
        return sum(losses) / len(losses)

    def discretize(self, a):
        probabilities = np.exp(a - max(a))
        probabilities = probabilities / sum(probabilities)
        return int(np.random.multinomial(1, probabilities)[0])

    def neural(self, x: np.ndarray, o: np.ndarray):
        o = o.ravel()
        if self.control == "linear":
            output = np.matmul(o, x[1:, :])
            output += x[0]
            return output.reshape(self.output_shape), np.zeros(0)
        if "structured" not in self.control:
            first_matrix = x[:self.first_size].reshape(self.first_layer_shape) / np.sqrt(len(o))
            second_matrix = x[self.first_size:(self.first_size + self.second_size)].reshape(self.second_layer_shape) / np.sqrt(self.num_neurons)
        else:
            assert len(x) == 2
            first_matrix = np.asarray(x[0][0])
            second_matrix = np.asarray(x[0][1])
            assert first_matrix.shape == self.first_layer_shape, f"{first_matrix} does not match {self.first_layer_shape}"
            assert second_matrix.shape == self.second_layer_shape, f"{second_matrix} does not match {self.second_layer_shape}"
        assert len(o) == len(
            first_matrix[1:]
        ), f"{o.shape} coming in matrix of shape {first_matrix.shape}"
        output = np.matmul(o, first_matrix[1:])
        if "deep" in self.control:
            current_index = self.first_size + self.second_size
            internal_layer_size = self.num_neurons ** 2
            s = (self.num_neurons, self.num_neurons)
            for k in range(self.num_internal_layers):
                output = np.tanh(output)
                output = np.matmul(output, x[current_index:current_index + internal_layer_size].reshape(s)) / np.sqrt(self.num_neurons)
                current_index += internal_layer_size
            assert current_index == len(x)
        output = np.matmul(np.tanh(output + first_matrix[0]), second_matrix)
        return output[self.memory_len :].reshape(self.output_shape), output[: self.memory_len]

    def gym_multi_function(self, x: np.ndarray):
        self.current_time_index = 0
        self.current_reward = 0
        self.current_observations = []
        self.current_actions = []
        loss = 0.0
        num_simulations = 7 if self.control != "conformant" and not self.randomized else 1
        for seed in range(num_simulations):
            loss += self.gym_simulate(x, seed=seed if not self.randomized else np.random.randint(500000))
        return loss / num_simulations

    def action_cast(self, a):
        env = self.env
        if type(a) == np.float64:
            a = np.asarray((a,))
        if self.discrete:
            a = self.discretize(a)
        else:
            if type(a) != self.action_type:  # , f"{a} does not have type {self.action_type}"
                a = self.action_type(a)
            try:
                if env.action_space.low is not None and env.action_space.high is not None:
                    # Projection to [0, 1]
                    a = 0.5 * (1.0 + np.tanh(a))
                    # Projection to the right space.
                    a = env.action_space.low + (env.action_space.high - env.action_space.low) * a
            except AttributeError:
                pass  # Sometimes an action space has no low and no high.
            if self.subaction_type is not None:
                if type(a) == tuple:
                    a = tuple(int(_a + 0.5) for _a in a)
                else:
                    for i in range(len(a)):
                        a[i] = self.subaction_type(a[i])
        assert type(a) == self.action_type, f"{a} should have type {self.action_type} "
        try:
            assert env.action_space.contains(
                a
            ), f"In {self.name}, high={env.action_space.high} low={env.action_space.low} {a} is not sufficiently close to {[env.action_space.sample() for _ in range(10)]}"
        except AttributeError:
            pass  # Not all env can do "contains".
        return a

    def step(self, a):
        o, r, done, info = self.env.step(a)
        self.current_time_index += 1
        self.current_reward += r
        self.current_observations += [np.asarray(o).copy()]
        self.current_actions += [np.asarray(a).copy()]
        if done:
            self.archive += [(self.current_observations, self.current_actions, self.current_reward)]
        return o, r, done, info

    def heuristic(self, o):
        current_observations = np.asarray(self.current_observations + [o], dtype=np.float32)
        assert len(current_observations) == 1 + self.current_time_index, f"{len(current_observations)} vs {self.current_time_index}"
        a = self.env.action_space.sample()
        best_a = None
        best_loss = float("Inf")
        for trace in self.archive:
            to, ta, tr = trace
            if len(current_observations) > len(to):
                continue
            to = np.asarray(to[:len(current_observations)], dtype=np.float32)
            if tr >= best_loss:
                continue
            #if all((_to - _o) for _to, _o in zip(to, current_observations)) <= 1e-7:
            if np.array_equal(to, current_observations):
                best_a = np.asarray(ta[len(current_observations) - 1], dtype=np.float32)
                best_loss = tr
        return best_a

    def gym_simulate(self, x: np.ndarray, seed: int = 0):
        try:
            if self.policy_shape is not None:
                x = x.reshape(self.policy_shape)
        except:
            assert False, f"x has shape {x.shape} and needs {self.policy_shape} for control {self.control}"
        assert seed == 0 or self.control != "conformant" or self.randomized
        env = self.env
        env.seed(seed=seed)
        o = env.reset()
        control = self.control
        if "conformant" in control:
            return self.gym_conformant(x)
        if "scrambled" in control:
            np.random.RandomState(1234).shuffle(x)
        if "noisy" in control:
            x = x + 0.01 * np.random.RandomState(1234).normal(size=x.shape)
        reward = 0.0
        memory = np.zeros(self.memory_len)
        for i in range(self.num_time_steps):
            if self.discrete_input:
                obs = np.zeros(shape=self.input_dim - self.extended_input_len - len(memory))
                obs[o] = 1
                o = obs
            previous_o = o
            o = np.concatenate([np.asarray(o).ravel(), memory.ravel(), self.extended_input])
            assert len(o) == self.input_dim, f"o has shape {o.shape} whereas input_dim={self.input_dim} ({control} / {env})"
            a, memory = self.neural(x[i % len(x)] if "multi" in control else x, o)
            a = self.action_cast(a)
            try:
                o, r, done, _ = self.step(a)  # Outputs = observation, reward, done, info.
            except AssertionError:  # Illegal action.
                return 1e20 / (1.0 + i)  # We encourage late failures rather than early failures.
            if "stacking" in control:
                attention_a = self.heuristic(o)  # Best so far, or something like that heuristically derived.
                if attention_a is not None:
                    a = attention_a
                additional_input = np.concatenate([np.asarray(a).ravel(), previous_o.ravel()])
                shift = len(additional_input)
                self.extended_input[:(len(self.extended_input) - shift)] = self.extended_input[shift:]
                self.extended_input[(len(self.extended_input) - shift):] = additional_input
            reward += r
            if done:
                break
        return -reward

    def gym_conformant(self, x: np.ndarray):
        reward = 0.0
        for i, a in enumerate(10.0 * x):
            a = self.action_cast(a)
            try:
                _, r, done, _ = self.step(a)  # Outputs = observation, reward, done, info.
            except AssertionError:  # Illegal action.
                return 1e20 / (1.0 + i)  # We encourage late failures rather than early failures.
            reward += r
            if done:
                break
        # env.render()  if you want to display.
        return -reward
