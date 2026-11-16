"""TensorFlow se importa solo en entrenamiento o inferencia."""
import os

def tensorflow(cfg):
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("OMP_NUM_THREADS", str(cfg.get("threads",2)))
    import tensorflow as tf
    try:
        tf.config.threading.set_intra_op_parallelism_threads(cfg.get("threads",2))
        tf.config.threading.set_inter_op_parallelism_threads(1)
    except RuntimeError:
        pass
    tf.keras.utils.set_random_seed(cfg["seed"])
    tf.config.experimental.enable_op_determinism()
    return tf

def build(tf, shape, classes, mean, variance):
    L = tf.keras.layers
    model = tf.keras.Sequential([
        L.Input(shape=shape),
        L.Normalization(axis=None, mean=float(mean), variance=float(variance)),
        L.Resizing(48,64),
        L.Conv2D(16,3,activation="relu",padding="same"), L.MaxPooling2D(),
        L.Conv2D(32,3,activation="relu",padding="same"), L.MaxPooling2D(),
        L.Conv2D(48,3,activation="relu",padding="same"), L.Flatten(),
        L.Dropout(.25), L.Dense(32,activation="relu"), L.Dense(classes,activation="softmax")])
    model.compile(optimizer=tf.keras.optimizers.Adam(.001),
                  loss="sparse_categorical_crossentropy",metrics=["accuracy"])
    return model
