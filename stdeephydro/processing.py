import copy
import logging
import xarray as xr

from stdeephydro import dataset

logger = logging.getLogger(__name__)


def merge_observations_and_predictions(ds_observation: xr.Dataset, ds_prediction: xr.Dataset,
                                       use_pred_timeframe: bool = True) -> xr.Dataset:
    """
    Merges two xarray.Datasets which contain observation and prediction timeseries data. Only variables that are
    present within the prediction dataset will be considered for subsetting the observation dataset. For each
    variable the resulting xarray.Dataset contains two variables, each one named by the original variable but with
    a prefix indicating observations or predictions. E.g. if the prediction dataset contains a variable named
    "streamflow", the resulting dataset contains two variables "streamflow_obs" and "streamflow_pred".
    By default, the prediction's timeframe will be used for merging both datasets.

    Parameters
    ----------
    ds_observation: xarray.Dataset
        Dataset that contains observations
    ds_prediction
        Dataset that contains predictions
    use_pred_timeframe: bool
        If True the prediction dataset timeframe should be used for merging both datasets. Otherwise, the observation
        dataset timeframe will be preserved.

    Returns
    -------
    xarray.Dataset
        Dataset containing merged observation and prediction timeseries

    """
    variables = list(ds_prediction.keys())

    if use_pred_timeframe:
        start_date = ds_prediction.time[0]
        end_date = ds_prediction.time[-1]
    else:
        start_date = ds_observation.time[0]
        end_date = ds_observation.time[-1]

    ds_obs = ds_observation[variables].sel(time=slice(start_date, end_date))
    ds_obs = ds_obs.rename(dict((param, param + "_obs") for param in variables))
    ds_prediction = ds_prediction.rename(dict((param, param + "_pred") for param in variables))

    return xr.merge([ds_prediction, ds_obs], join="left") \
        if use_pred_timeframe \
        else xr.merge([ds_prediction, ds_obs], join="right")


class AbstractProcessor:
    """
    Abstract processor base class, which can be subclassed for implementing custom data processing pipelines

    Parameters
    ----------
    variables: List of str
        List of variables that should be considered for data processing
    scaling_params: tuple
        Tuple of parameters used for min/max scaling data scaling
    """
    def __init__(self, variables: list = None, scaling_params: tuple = None):
        self.__variables = variables
        self.__scaling_params = scaling_params

    @property
    def variables(self):
        return self.__variables

    @variables.setter
    def variables(self, value):
        self.__variables = value

    @property
    def scaling_params(self):
        return self.__scaling_params

    @scaling_params.setter
    def scaling_params(self, value):
        self.__scaling_params = value

    def fit(self, ds: dataset.HydroDataset):
        """
        Fits the processor to a dataset, to derive certain parameters that should be used for processing other datasets.

        For instance, to perform min/max scaling on validation and test datasets, minimum and maximum variable values
        may be derived from a training dataset.

        Parameters
        ----------
        ds: dataset.HydroDataset
            Dataset that will be used for fitting the processor by deriving processing parameters from it.
        """
        pass

    def process(self, ds: dataset.HydroDataset) -> dataset.HydroDataset:
        """
        Performs various preprocessing steps on a dataset

        Parameters
        ----------
        ds: dataset.HydroDataset
            Dataset that will be processed

        Returns
        -------
        dataset.HydroDataset
            Resulting dataset after processing
        """
        pass

    def scale(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Performs a min/max scaling on all variables of a xarray.Dataset. If the current processor instance has been
        fit to a dataset, scaling will be done by using the minimum and maximum parameters from the fitting dataset.
        Else, minimum and maximum parameters will be calculated from the given xarray.Dataset.

        Parameters
        ----------
        ds: xarray.Dataset
            Timeseries data which will be scaled.

        Returns
        -------
        xr.Dataset
            The scaled dataset
        """
        if self.scaling_params is None:
            min_params = ds.min()
            max_params = ds.max()
        else:
            min_params, max_params = self.scaling_params
        return (ds - min_params) / (max_params - min_params)

    def rescale(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Rescales all variables of a xarray.Dataset. Therefore minimum and maximum parameters from the fitting dataset
        will be used for rescaling.

        Parameters
        ----------
        ds: xarray.Dataset
            Timeseries data which will be rescaled.

        Returns
        -------
        xr.Dataset
            The rescaled dataset
        """
        min_params, max_params = self.scaling_params
        return ds * (max_params - min_params) + min_params

    def fillna(self, ds: xr.Dataset, value: int) -> xr.Dataset:
        """
        Fills NaN values of the specified variables with an arbitrary value

        Parameters
        ----------
        ds: xr.Dataset
            Dataset
        value: int
            Used for filling NaN values within the dataset

        Returns
        -------
        xr.Dataset
            The resulting dataset
        """
        ds[self.variables] = ds[self.variables].fillna(value)
        return ds

    def setna(self, ds: xr.Dataset, value: int):
        """
        Sets certain values of a dataset to NaN

        Parameters
        ----------
        ds: xr.Dataset
            Dataset
        value: int
            Elements with this value will be set to NaN

        Returns
        -------
        xr.Dataset
            The resulting dataset
        """
        for f in self.variables:
            ds[f] = ds[f].where(ds[f] != value)
        return ds


class DefaultDatasetProcessor(AbstractProcessor):
    """
    Performs several processing steps on timeseries data wrapped by a dataset.HydroDataset instance:

    1. Performs min/max scaling on all dataset variables
    2. Replaces NaN values of the specified variables with -1


    Parameters
    ----------
    variables: list
        List of variables names that will be considered for certain processing routines
    scaling_params: tuple
        Parameters that should be used for performing min-max-scaling on the timeseries data.
    """

    def __init__(self, variables: list = None, scaling_params: tuple = None):
        super().__init__(variables, scaling_params)

    def fit(self, ds: dataset.HydroDataset):
        """
        Fits the processor to a dataset which usually should be the training dataset. Fitting means, the processor will
        derive various parameters from the specified dataset which will be used for several subsequent processing steps.
        Usually, you will fit the processor on the training data to use the derived parameters for processing the
        validation and test datasets.

        Up to now, this method will derive the following parameters:
        - Minimum and maximum values for each variable, which will be used for performing a min-max-scaling.

        Parameters
        ----------
        ds: dataset.HydroDataset
            Dataset that holds timeseries data as xarray.Dataset

        """
        self.__fit_scaling_params(ds)
        self.variables = ds.feature_cols

    def process(self, ds: dataset.HydroDataset):
        """
        Performs several processing steps on a dataset.LumpedDataset.

        Note, that it will use parameters that have been derived while fitting the processor to a dataset using the fit
        function. If this function has not been called  before, it will automatically derive the same parameters form
        the specified dataset. This will lead to  misleading results if you aim to process validation and test datasets
        by using processing parameters derived from a training dataset. Hence, it is strongly recommended to first call
        fit() on a dedicated dataset.

        Parameters
        ----------
        ds: dataset.HydroDataset
            Dataset that will be processed

        Returns
        -------
            The resulting dataset.BasinDataset after performing various processing steps on it

        """
        if self.scaling_params is None:
            logger.warning("Processor has not been fit to a dataset before. Thus, it will be fitted to the provided "
                           "dataset.")
            self.__fit_scaling_params(ds)
        ds = copy.copy(ds)
        ds.timeseries = self.scale(ds.timeseries)
        ds.timeseries = self.fillna(ds.timeseries, -1)
        return ds

    def __fit_scaling_params(self, ds: dataset.HydroDataset):
        if all(i in ds.timeseries.coords for i in ["basin", "time", "y", "x"]):
            self.scaling_params = (ds.timeseries.min(["time", "y", "x"]), ds.timeseries.max(["time", "y", "x"]))
        elif all(i in ds.timeseries.coords for i in ["basin", "time"]):
            self.scaling_params = (ds.timeseries.min(["time"]), ds.timeseries.max(["time"]))
        else:
            raise ValueError(f"Coordinates should contain one of the sets: ['basin', 'time'],"
                             f"['basin', 'time', 'y', 'x']. Actual coordinates are: {list(ds.timeseries.coords)}")
