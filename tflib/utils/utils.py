import numpy as np
import tensorflow as tf


def init(checkpoint_directory,
         checkpoint_kwargs=None,
         checkpoint_max_to_keep=5,
         checkpoint_keep_checkpoint_every_n_hours=None,
         counter_start=0,
         counter_scope=None,
         session=None):
    """Run codes that are commonly used by LynnHo."""
    session = tf.get_default_session() if session is None else session

    # step counter
    step_cnt, update_cnt = counter(start=counter_start, scope=counter_scope)

    # initialize variables
    session.run(tf.initializers.global_variables())

    # initialize writers
    session.run(tf.contrib.summary.summary_writer_initializer_op())

    # checkpoint
    checkpoint = Checkpoint(checkpoint_directory,
                            checkpoint_kwargs=checkpoint_kwargs,
                            max_to_keep=checkpoint_max_to_keep,
                            keep_checkpoint_every_n_hours=checkpoint_keep_checkpoint_every_n_hours)
    checkpoint.restore().initialize_or_restore(session=session)

    return checkpoint, step_cnt, update_cnt


def session(graph=None,
            allow_soft_placement=True,
            log_device_placement=False,
            allow_growth=True):
    """Return a Session with simple config."""
    config = tf.ConfigProto(allow_soft_placement=allow_soft_placement,
                            log_device_placement=log_device_placement)
    config.gpu_options.allow_growth = allow_growth
    return tf.Session(graph=graph, config=config)


class Checkpoint:
    """Enhanced tf.train.Checkpoint.

    Parameters
    ----------
    directory: str
        To be passed to tf.train.CheckpointManager.
    checkpoint_kwargs:
        To be passed to tf.train.Checkpoint. Default as `{v.name: v for v in tf.global_variables()}`.

    """

    def __init__(self,
                 directory,  # for tf.train.CheckpointManager
                 checkpoint_kwargs=None,  # for tf.train.Checkpoint
                 max_to_keep=5,
                 keep_checkpoint_every_n_hours=None):
        # default to save all variables
        checkpoint_kwargs = {v.name: v for v in tf.global_variables()} if checkpoint_kwargs is None else checkpoint_kwargs
        self.checkpoint = tf.train.Checkpoint(**checkpoint_kwargs)
        self.manager = tf.train.CheckpointManager(self.checkpoint, directory, max_to_keep, keep_checkpoint_every_n_hours)

    def restore(self, save_path=None):
        save_path = self.manager.latest_checkpoint if save_path is None else save_path
        return self.checkpoint.restore(save_path)

    def save(self, file_prefix_or_checkpoint_number=None, session=None):
        if isinstance(file_prefix_or_checkpoint_number, str):
            return self.checkpoint.save(file_prefix_or_checkpoint_number, session=session)
        else:
            with (tf.get_default_session() if session is None else session).as_default():
                return self.manager.save(checkpoint_number=file_prefix_or_checkpoint_number)

    def __getattr__(self, attr):
        if hasattr(self.checkpoint, attr):
            return getattr(self.checkpoint, attr)
        elif hasattr(self.manager, attr):
            return getattr(self.manager, attr)
        else:
            self.__getattribute__(attr)  # this will raise an exception


def counter(start=0, scope=None):
    with tf.variable_scope(scope, 'counter'):
        counter = tf.get_variable(name='counter',
                                  initializer=tf.constant_initializer(start),
                                  shape=(),
                                  dtype=tf.int64)
        update_cnt = tf.assign(counter, tf.add(counter, 1))
        return counter, update_cnt


def receptive_field(convnet_fn):
    # TODO(Lynn): too ugly ...
    g = tf.Graph()
    with g.as_default():
        img = tf.placeholder(tf.float32, shape=(1, None, None, 3), name='img')
        convnet_fn(img)

    node_names = [node.name for node in g.as_graph_def().node
                  if 'img' != node.name
                  # for Conv
                  if 'weights' not in node.name
                  if 'biases' not in node.name
                  if 'dilation_rate' not in node.name
                  # for BatchNorm
                  if 'beta' not in node.name
                  if 'gamma' not in node.name
                  if 'moving_mean' not in node.name
                  if 'moving_variance' not in node.name
                  if 'AssignMovingAvg' not in node.name]

    results = []
    for node_name in node_names:
        try:
            rf_x, rf_y, eff_stride_x, eff_stride_y, eff_pad_x, eff_pad_y = \
                tf.contrib.receptive_field.compute_receptive_field_from_graph_def(g.as_graph_def(), 'img', node_name)
            results.append((
                node_name,
                {'receptive_field_x': rf_x,
                 'receptive_field_y': rf_y,
                 'effective_stride_x': eff_stride_x,
                 'effective_stride_y': eff_stride_y,
                 'effective_padding_x': eff_pad_x,
                 'effective_padding_y': eff_pad_y}
            ))
        except ValueError as e:
            if str(e) != "Output node was not found":
                raise e

    return results


def count_parameters(variables):
    variables = variables if isinstance(variables, (list, tuple)) else [variables]
    n_params = np.sum([np.prod(v.shape.as_list()) for v in variables])
    n_bytes = np.sum([np.prod(v.shape.as_list()) * v.dtype.size for v in variables])
    return n_params, n_bytes


def print_tensor(tensors):
    if not isinstance(tensors, (list, tuple)):
        tensors = [tensors]

    for i, tensor in enumerate(tensors):
        ctype = str(type(tensor))
        if 'Tensor' in ctype:
            print('%d: %s("%s", shape=%s, dtype=%s, device=%s)' %
                  (i, 'Tensor', tensor.name, tensor.shape, tensor.dtype.name, tensor.device))
        elif 'Variable' in ctype:
            print('%d: %s("%s", shape=%s, dtype=%s, device=%s)' %
                  (i, 'Variable', tensor.name, tensor.shape, tensor.dtype.name, tensor.device))
        elif 'Operation' in ctype:
            print('%d: %s("%s", device=%s)' %
                  (i, 'Operation', tensor.name, tensor.device))
        else:
            raise Exception('Not a Tensor, Variable or Operation!')


prt = print_tensor
