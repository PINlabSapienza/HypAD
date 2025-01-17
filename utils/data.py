# -*- coding: utf-8 -*-

"""
Data Management module.

This module contains functions that allow downloading demo data from Amazon S3,
as well as load and work with other data stored locally.

The demo data is a modified version of the NASA data found here:

https://s3-us-west-2.amazonaws.com/telemanom/data.zip
"""

import json
import logging
import os

import numpy as np
import pandas as pd

from utils.dataloader import SignalDataset
from utils.dataloader_multivariate import MultivariateDataset

LOGGER = logging.getLogger(__name__)

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BUCKET = "d3-ai-orion"
S3_URL = "https://{}.s3.amazonaws.com/{}"

NASA_SIGNALS = (
    "P-1",
    "S-1",
    "E-1",
    "E-2",
    "E-3",
    "E-4",
    "E-5",
    "E-6",
    "E-7",
    "E-8",
    "E-9",
    "E-10",
    "E-11",
    "E-12",
    "E-13",
    "A-1",
    "D-1",
    "P-3",
    "D-2",
    "D-3",
    "D-4",
    "A-2",
    "A-3",
    "A-4",
    "G-1",
    "G-2",
    "D-5",
    "D-6",
    "D-7",
    "F-1",
    "P-4",
    "G-3",
    "T-1",
    "T-2",
    "D-8",
    "D-9",
    "F-2",
    "G-4",
    "T-3",
    "D-11",
    "D-12",
    "B-1",
    "G-6",
    "G-7",
    "P-7",
    "R-1",
    "A-5",
    "A-6",
    "A-7",
    "D-13",
    "A-8",
    "A-9",
    "F-3",
    "M-6",
    "M-1",
    "M-2",
    "S-2",
    "P-10",
    "T-4",
    "T-5",
    "F-7",
    "M-3",
    "M-4",
    "M-5",
    "P-15",
    "C-1",
    "C-2",
    "T-12",
    "T-13",
    "F-4",
    "F-5",
    "D-14",
    "T-9",
    "P-14",
    "T-8",
    "P-11",
    "D-15",
    "D-16",
    "M-7",
    "F-8",
)


def download(name, test_size=None, data_path=DATA_PATH):
    """Load the CSV with the given name from S3.

    If the CSV has never been loaded before, it will be downloaded
    from the [d3-ai-orion bucket](https://d3-ai-orion.s3.amazonaws.com) or
    the S3 bucket specified following the `s3://{bucket}/path/to/the.csv` format,
    and then cached inside the `data` folder, within the `orion` package
    directory, and then returned.

    Otherwise, if it has been downloaded and cached before, it will be directly
    loaded from the `orion/data` folder without contacting S3.

    If a `test_size` value is given, the data will be split in two parts
    without altering its order, making the second one proportionally as
    big as the given value.

    Args:
        name (str): Name of the CSV to load.
        test_size (float): Value between 0 and 1 indicating the proportional
            size of the test split. If 0 or None (default), the data is not split.

    Returns:
        If no test_size is given, a single pandas.DataFrame is returned containing all
        the data. If test_size is given, a tuple containing one pandas.DataFrame for
        the train split and another one for the test split is returned.
    """

    url = None
    if name.startswith("s3://"):
        parts = name[5:].split("/", 1)
        bucket = parts[0]
        path = parts[1]
        url = S3_URL.format(bucket, path)

        filename = os.path.join(data_path, path.split("/")[-1])
    else:
        filename = os.path.join(data_path, name + ".csv")

    if os.path.exists(filename):
        data = pd.read_csv(filename)
    else:
        url = url or S3_URL.format(BUCKET, "{}.csv".format(name))

        LOGGER.info("Downloading CSV %s from %s", name, url)
        os.makedirs(data_path, exist_ok=True)
        print(url)
        data = pd.read_csv(url)
        data.to_csv(filename, index=False)

    return data


def download_demo(path="orion-data", split=False):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

    LOGGER.info("Downloading Orion Demo Data to folder %s", path)
    for signal in NASA_SIGNALS[0:3]:
        if split:
            download(signal + "-train", data_path=path)
            download(signal + "-test", data_path=path)
        else:
            download(signal, data_path=path)


def load_csv(path, timestamp_column=None, value_column=None):
    header = None if timestamp_column is not None else "infer"
    data = pd.read_csv(path, header=header)

    if timestamp_column is None:
        if value_column is not None:
            raise ValueError(
                "If value_column is provided, timestamp_column must be as well"
            )

        return data

    elif value_column is None:
        raise ValueError(
            "If timestamp_column is provided, value_column must be as well"
        )
    elif timestamp_column == value_column:
        raise ValueError("timestamp_column cannot be the same as value_column")

    timestamp_column_name = data.columns[timestamp_column]
    value_column_name = data.columns[value_column]
    columns = {
        "timestamp": data[timestamp_column_name].values,
        "value": data[value_column_name].values,
    }

    return pd.DataFrame(columns)[["timestamp", "value"]]


def load_signal(signal, test_size=None, timestamp_column=None, value_column=None):
    if os.path.isfile(signal):
        data = load_csv(signal, timestamp_column, value_column)
    else:
        data = download(signal)

    data["timestamp"] = data["timestamp"].astype(int)
    data["value"] = data["value"].astype(float)

    if test_size is None:
        return data

    test_length = round(len(data) * test_size)
    train = data.iloc[:-test_length]
    test = data.iloc[-test_length:]

    return train, test


def load_anomalies(signal, edges=False):
    anomalies = download("anomalies")

    anomalies = anomalies.set_index("signal").loc[signal].values[0]
    anomalies = pd.DataFrame(json.loads(anomalies), columns=["start", "end"])

    if edges:
        data = download(signal)
        start = data.timestamp.min()
        end = data.timestamp.max()

        anomalies["score"] = 1
        parts = np.concatenate(
            [
                [[start, anomalies.start.min(), 0]],
                anomalies.values,
                [[anomalies.end.max(), end, 0]],
            ],
            axis=0,
        )
        anomalies = pd.DataFrame(parts, columns=["start", "end", "score"])

    return anomalies


def dataset_selection(params):
    """
    DATASET SELECTION
    """

    read_path = ""
    # original CASAS dataset (test==train).
    if params.dataset == "CASAS_":
        path = "path_to_CASAS"
        train_dataset = MultivariateDataset(
            seq_path=path + "sequences_2week_{}.pt".format(params.signal),
            gt_path=path + "ground_truth_2week_{}.pt".format(params.signal),
            split=params.split,
        )
        test_dataset = MultivariateDataset(
            seq_path=path + "sequences_2week_{}.pt".format(params.signal),
            gt_path=path + "ground_truth_2week_{}.pt".format(params.signal),
            test=True,
        )

    # new_CASAS is the dataset proposed for CVPR '21 where the train&test splits have been created
    elif params.dataset == "new_CASAS":
        path = "path_to_new_CASAS"
        train_dataset = MultivariateDataset(
            seq_path=path + params.signal,
            gt_path=path + params.signal,
            split=params.split,
            dataset=params.dataset,
        )
        test_dataset = MultivariateDataset(
            seq_path=path + params.signal,
            gt_path=path + params.signal,
            test=True,
            dataset=params.dataset,
        )

    elif params.dataset == "SWAT":
        path = "./data/SWAT/"
        train_dataset = MultivariateDataset(dataset=params.dataset)
        test_dataset = MultivariateDataset(test=True, dataset=params.dataset)

    elif params.dataset == "WADI":
        path = "./data/WADI_downsampled/"
        train_dataset = MultivariateDataset(dataset=params.dataset)
        test_dataset = MultivariateDataset(test=True, dataset=params.dataset)

    elif params.dataset in ["CASAS", "ELINUS", "eHealth"]:
        if not params.new_features:
            seq_path = "./data/DATASETS/{}/normal_sequences.pt".format(params.dataset)
            seq_path_test = "./data/DATASETS/{}/POINTS/{}/{}_sequences_id{}.pt".format(
                params.dataset, params.signal, params.signal, params.id
            )
            gt_path = "./data/DATASETS/{}/POINTS/{}/{}_groundtruth_id{}.pt".format(
                params.dataset, params.signal, params.signal, params.id
            )
        else:
            seq_path = "./data/DATASETS/{}/normal_sequences_newfeatures.pt".format(
                params.dataset
            )
            seq_path_test = "./data/DATASETS/{}/POINTS_NEWFEATURES/{}_sequences_newfeatures.pt".format(
                params.dataset, params.signal, params.signal
            )
            gt_path = "./data/DATASETS/{}/POINTS_NEWFEATURES/{}_groundtruth_newfeatures.pt".format(
                params.dataset, params.signal, params.signal
            )

        train_dataset = MultivariateDataset(
            seq_path=seq_path,
            gt_path=gt_path,
            split=params.split,
            dataset=params.dataset,
        )
        test_dataset = MultivariateDataset(
            seq_path=seq_path_test, gt_path=gt_path, test=True, dataset=params.dataset
        )

    else:
        # univariate dataset with train=test
        if params.unique_dataset:
            # train_data = load_signal(params.signal)
            # test_data = load_signal(params.signal)
            train_dataset = SignalDataset(
                path="./data/{}.csv".format(params.signal), interval=params.interval
            )
            test_dataset = SignalDataset(
                path="./data/{}.csv".format(params.signal),
                test=True,
                interval=params.interval,
            )
            read_path = "./data/{}.csv".format(params.signal)

        # YAHOO dataset
        elif params.dataset in ["A1", "A2", "A3", "A4"]:
            train_dataset = SignalDataset(
                path="./data/YAHOO/{}Benchmark/{}.csv".format(
                    params.dataset, params.signal
                ),
                interval=1,
                yahoo=True,
            )
            test_dataset = SignalDataset(
                path="./data/YAHOO/{}Benchmark/{}.csv".format(
                    params.dataset, params.signal
                ),
                test=True,
                interval=1,
                yahoo=True,
            )
            read_path = "./data/YAHOO/{}Benchmark/{}.csv".format(
                params.dataset, params.signal
            )

        # univariate dataset with train!=test
        else:
            # train_data = load_signal(params.signal +'-train')
            # test_data = load_signal(params.signal +'-test')
            train_dataset = SignalDataset(
                path="./data/{}-train.csv".format(params.signal),
                interval=params.interval,
            )
            test_dataset = SignalDataset(
                path="./data/{}-test.csv".format(params.signal),
                interval=params.interval,
                test=True,
            )
            read_path = "./data/{}-test.csv".format(params.signal)

    return train_dataset, test_dataset, read_path  # type: ignore
