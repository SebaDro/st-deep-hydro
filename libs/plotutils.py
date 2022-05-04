import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import tensorflow as tf
import xarray as xr


def plot_loss(history: tf.keras.callbacks.History):
    """
    Visualizes the progress of a trained model by plotting the loss per epoch

    Parameters
    ----------
    history: tf.keras.callbacks.History
        A Tensorflow history object that holds information about training progress

    """
    plt.plot(history.history['loss'], label='Loss')
    plt.plot(history.history['val_loss'], label='Validation Loss')
    plt.xlabel('Epoche')
    plt.ylabel('RMSE')
    plt.legend()
    plt.grid(True)


def plot_predictions(ds: xr.Dataset, variable: str, basins: list = None):
    if basins is None:
        basins = ds.basin.values
    nr_basins = len(basins)
    if nr_basins == 1:
        plot_prediction_for_single_basin(ds, basins[0], variable)
    elif nr_basins > 1:
        fig, axis = plt.subplots(1, nr_basins, figsize=(16, 10))
        for ax, basin in zip(axis, basins):
            plot_prediction_for_single_basin(ds, basin, variable, ax)
    else:
        raise ValueError("There must be one basin for plotting, at least!")


def plot_prediction_for_single_basin(ds:  xr.Dataset, basin: str, variable: str, ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(16, 10))
    ds.sel(basin=basin)[f"{variable}_pred"].plot(ax=ax, label="prediction", zorder=1)
    ds.sel(basin=basin)[f"{variable}_obs"].plot(ax=ax, label="observation", zorder=0)
    ax.set_xlabel("time")
    ax.set_ylabel(variable)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%b"))
    ax.set_title(basin)
    ax.legend()