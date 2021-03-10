# Copyright 2021, Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for tree aggregation."""
import math
from absl.testing import parameterized

import tensorflow as tf
from dp_ftrl import tree_aggregation


class TreeAggregatorTest(tf.test.TestCase, parameterized.TestCase):

  @parameterized.named_parameters(
      ('total4_step1', 4, [1, 1, 2, 1], 1),
      ('total5_step1', 5, [1, 1, 2, 1, 2], 1),
      ('total6_step1', 6, [1, 1, 2, 1, 2, 2], 1),
      ('total7_step1', 7, [1, 1, 2, 1, 2, 2, 3], 1),
      ('total8_step1', 8, [1, 1, 2, 1, 2, 2, 3, 1], 1),
      ('total8_step2', 8, [2, 2, 4, 2, 4, 4, 6, 2], 2),
      ('total8_step0d5', 8, [0.5, 0.5, 1, 0.5, 1, 1, 1.5, 0.5], 0.5))
  def test_tree_sum_steps_expected(self, total_steps, expected_values,
                                   step_value):
    tree_aggregator = tree_aggregation.TFTreeAggregator(
        new_value_fn=lambda: step_value)
    state = tree_aggregator.init_state()
    for leaf_node_idx in range(total_steps):
      val, state = tree_aggregator.get_cumsum_and_update(state)
      self.assertEqual(leaf_node_idx + 1,
                       tree_aggregation.get_step_idx(state.level_state))
      self.assertEqual(expected_values[leaf_node_idx], val)

  @parameterized.named_parameters(
      ('total16_step1', 16, 1, 1),
      ('total17_step1', 17, 2, 1),
      ('total18_step1', 18, 2, 1),
      ('total19_step1', 19, 3, 1),
      ('total20_step0d5', 20, 1, 0.5),
      ('total21_step2', 21, 6, 2),
      # the following tests are slow.
      # ('total1024_step1', 1024, 1, 1),
      # ('total1025_step1', 1025, 2, 1),
      # ('total1026_step1', 1026, 2, 1),
      # ('total1027_step1', 1027, 3, 1),
      # ('total1028_step0d5', 1028, 1, 0.5),
      # ('total1029_step2', 1029, 6, 2),
  )
  def test_tree_sum_last_step_expected(self, total_steps, expected_value,
                                       step_value):
    tree_aggregator = tree_aggregation.TFTreeAggregator(
        new_value_fn=lambda: step_value)
    state = tree_aggregator.init_state()
    for leaf_node_idx in range(total_steps):
      val, state = tree_aggregator.get_cumsum_and_update(state)
    self.assertEqual(leaf_node_idx + 1,
                     tree_aggregation.get_step_idx(state.level_state))
    self.assertEqual(expected_value, val)

  @parameterized.named_parameters(
      ('total8_step1', 8, 1),
      ('total8_step2', 8, 2),
      ('total8_step0d5', 8, 0.5),
      # the following tests are slow.
      # ('total32_step0d5', 32, 0.5), ('total1024_step0d5', 1024, 0.5),
      # ('total2020_step0d5', 2020, 0.5), ('total64k_step0d5', 64000, 0.5),
  )
  def test_tree_sum_steps_max(self, total_steps, step_value):
    tree_aggregator = tree_aggregation.TFTreeAggregator(
        new_value_fn=lambda: step_value)
    max_val = step_value * math.ceil(math.log2(total_steps))
    state = tree_aggregator.init_state()
    for leaf_node_idx in range(total_steps):
      val, state = tree_aggregator.get_cumsum_and_update(state)
      self.assertEqual(leaf_node_idx + 1,
                       tree_aggregation.get_step_idx(state.level_state))
      self.assertLessEqual(val, max_val)

  @parameterized.named_parameters(
      ('total4_std1_d1000', 4, [1, 1, 2, 1], 1, [1000], 0.1),
      ('total4_std1_d10000', 4, [1, 1, 2, 1], 1, [10000], 0.03),
      ('total7_std1_d1000', 7, [1, 1, 2, 1, 2, 2, 3], 1, [1000], 0.1),
      ('total8_std1_d1000', 8, [1, 1, 2, 1, 2, 2, 3, 1], 1, [1000], 0.1),
      ('total8_std2_d1000', 8, [4, 4, 8, 4, 8, 8, 12, 4], 2, [1000], 0.1),
      ('total8_std0d5_d1000', 8, [0.25, 0.25, 0.5, 0.25, 0.5, 0.5, 0.75, 0.25
                                 ], 0.5, [1000], 0.1))
  def test_tree_sum_noise_expected(self, total_steps, expected_variance,
                                   noise_std, variable_shape, tolerance):

    random_generator = tf.random.Generator.from_seed(0)

    def get_noise():
      return random_generator.normal(shape=variable_shape, stddev=noise_std)

    tree_aggregator = tree_aggregation.TFTreeAggregator(new_value_fn=get_noise)
    state = tree_aggregator.init_state()
    for leaf_node_idx in range(total_steps):
      val, state = tree_aggregator.get_cumsum_and_update(state)
      self.assertEqual(leaf_node_idx + 1,
                       tree_aggregation.get_step_idx(state.level_state))
      self.assertAllClose(
          expected_variance[leaf_node_idx],
          tf.math.reduce_variance(val),
          rtol=tolerance)

  @parameterized.named_parameters(
      ('val0', 0, [0], [1]),
      ('val1', 1, [1], [0, 1]),
      ('val2', 2, [0, 1], [1, 1]),
      ('val3', 3, [1, 1], [0, 0, 1]),
      ('val8', 8, [0, 0, 0, 1], [1, 0, 0, 1]),
      ('val9', 9, [1, 0, 0, 1], [0, 1, 0, 1]),
      ('val10', 10, [0, 1, 0, 1], [1, 1, 0, 1]),
  )
  def test_update_level_state(self, val, state_in, expected_state_out):
    tree_aggregator = tree_aggregation.TFTreeAggregator(new_value_fn=None)
    state_out = tree_aggregator._update_level_state(
        tf.constant(state_in, dtype=tf.int8))
    self.assertAllEqual(expected_state_out, state_out)
    self.assertEqual(val + 1, tree_aggregation.get_step_idx(state_out))

  def test_cumsum_vector(self, total_steps=15):

    def new_value_fn():
      return [
          tf.ones([2, 2], dtype=tf.float32),
          tf.constant([2], dtype=tf.float32)
      ]

    tree_aggregator = tree_aggregation.TFTreeAggregator(
        new_value_fn=new_value_fn)
    tree_aggregator_truth = tree_aggregation.TFTreeAggregator(
        new_value_fn=lambda: 1)
    state = tree_aggregator.init_state()
    truth_state = tree_aggregator_truth.init_state()
    for leaf_node_idx in range(total_steps):
      val, state = tree_aggregator.get_cumsum_and_update(state)
      expected_val, truth_state = tree_aggregator_truth.get_cumsum_and_update(
          truth_state)
      self.assertEqual(
          tree_aggregation.get_step_idx(state.level_state),
          tree_aggregation.get_step_idx(truth_state.level_state))
      self.assertEqual(leaf_node_idx + 1,
                       tree_aggregation.get_step_idx(truth_state.level_state))
      expected_result = [
          expected_val * tf.ones([2, 2], dtype=tf.float32),
          expected_val * tf.constant([2], dtype=tf.float32),
      ]
      tf.nest.map_structure(self.assertAllEqual, val, expected_result)


if __name__ == '__main__':
  tf.test.main()
